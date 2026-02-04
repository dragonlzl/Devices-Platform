import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import httpx
import os
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import db_session, init_db, now_iso
from .llm import LLMError, call_llm
from .notify import NotifyError, send_feishu_message
from .schemas import (
    BorrowRequest,
    BorrowerChangeRequest,
    DeviceCreate,
    DeviceUpdate,
    ExtendRequest,
    LLMModelCreate,
    LLMModelAssignRequest,
    LLMModelUpdate,
    LLMTestRequest,
    SettingUpdate,
    SystemCreate,
    SystemDeleteRequest,
    SystemUpdate,
    VendorCreate,
    VendorDeleteRequest,
    VendorUpdate,
    VersionCreate,
    VersionDeleteRequest,
    VersionUpdate,
)


BASE_DIR = Path(__file__).resolve()
BACKEND_DIR = BASE_DIR.parent
REPO_DIR = BACKEND_DIR.parent

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_root = REPO_DIR / "frontend"
frontend_dist = frontend_root / "dist"
frontend_dir = frontend_dist if frontend_dist.exists() else frontend_root
app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


@app.get("/")
async def root():
    return {"message": "Device Loan Assistant API"}


@app.get("/admin")
async def admin_page():
    return FileResponse(str(frontend_dir / "admin.html"))


@app.get("/borrow")
async def borrow_page():
    return FileResponse(str(frontend_dir / "borrow.html"))


def _ensure_required(value: Optional[str], label: str):
    if value is None or not str(value).strip():
        raise HTTPException(status_code=400, detail=f"{label}不能为空")


def _parse_datetime(value: str) -> datetime:
    try:
        cleaned = value.replace("Z", "+00:00") if value.endswith("Z") else value
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"时间格式错误: {exc}")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


LOCAL_TZ = timezone(timedelta(hours=8))


def _format_notify_time(value: Optional[Union[str, datetime]]) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = _parse_datetime(value)
    return parsed.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row) -> Dict[str, Any]:
    return dict(row) if row else {}


def _get_setting(conn, key: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return row["value"]
    return ""


def _set_setting(conn, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _delete_setting(conn, key: str) -> None:
    conn.execute("DELETE FROM settings WHERE key = ?", (key,))


def _get_int_setting(conn, key: str) -> Optional[int]:
    value = _get_setting(conn, key)
    if value and value.isdigit():
        return int(value)
    return None


def _insert_borrow_record(
    conn,
    device_id: int,
    device_model: str,
    borrower_name: str,
    borrowed_at: str,
    expected_return_at: Optional[str],
    request_id: Optional[int],
) -> None:
    now = now_iso()
    conn.execute(
        """
        INSERT INTO borrow_records (
            device_id, device_model, borrower_name, borrowed_at, expected_return_at,
            returned_at, status, request_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, NULL, 'borrowed', ?, ?, ?)
        """,
        (
            device_id,
            device_model,
            borrower_name,
            borrowed_at,
            expected_return_at,
            request_id,
            now,
            now,
        ),
    )


def _update_borrow_record_expected(conn, device_id: int, expected_return_at: str) -> None:
    now = now_iso()
    conn.execute(
        """
        UPDATE borrow_records
        SET expected_return_at = ?, updated_at = ?
        WHERE id = (
            SELECT id FROM borrow_records
            WHERE device_id = ? AND returned_at IS NULL
            ORDER BY borrowed_at DESC
            LIMIT 1
        )
        """,
        (expected_return_at, now, device_id),
    )


def _close_borrow_record(conn, device_id: int, returned_at: str) -> None:
    now = now_iso()
    conn.execute(
        """
        UPDATE borrow_records
        SET returned_at = ?, status = 'returned', updated_at = ?
        WHERE id = (
            SELECT id FROM borrow_records
            WHERE device_id = ? AND returned_at IS NULL
            ORDER BY borrowed_at DESC
            LIMIT 1
        )
        """,
        (returned_at, now, device_id),
    )


def _assign_llm_model(conn, model_id: int, role: str) -> None:
    role_value = role.strip().lower()
    if role_value not in ("fast", "accurate"):
        raise HTTPException(status_code=400, detail="角色必须为 fast 或 accurate")
    row = conn.execute("SELECT id FROM llm_models WHERE id = ?", (model_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="模型不存在")
    fast_id = _get_int_setting(conn, "llm_fast_model_id")
    accurate_id = _get_int_setting(conn, "llm_accurate_model_id")
    if role_value == "fast":
        if accurate_id == model_id:
            raise HTTPException(status_code=400, detail="更快模型不能与更准模型相同")
        _set_setting(conn, "llm_fast_model_id", str(model_id))
    else:
        if fast_id == model_id:
            raise HTTPException(status_code=400, detail="更准模型不能与更快模型相同")
        _set_setting(conn, "llm_accurate_model_id", str(model_id))


def _clear_llm_assignment(conn, role: str) -> None:
    role_value = role.strip().lower()
    if role_value not in ("fast", "accurate"):
        raise HTTPException(status_code=400, detail="角色必须为 fast 或 accurate")
    key = "llm_fast_model_id" if role_value == "fast" else "llm_accurate_model_id"
    _delete_setting(conn, key)


def _validate_version_for_system(conn, system_id: int, version_id: int) -> None:
    row = conn.execute(
        "SELECT id FROM system_versions WHERE id = ? AND system_id = ?",
        (version_id, system_id),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="系统版本不匹配")


def _fetch_devices(conn, query: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = (
        "SELECT d.*, v.name AS vendor_name, s.name AS system_name, sv.version AS system_version "
        "FROM devices d "
        "JOIN vendors v ON d.vendor_id = v.id "
        "JOIN systems s ON d.system_id = s.id "
        "JOIN system_versions sv ON d.system_version_id = sv.id "
    )
    params: List[Any] = []
    if query:
        like = f"%{query}%"
        sql += (
            "WHERE CAST(d.id AS TEXT) LIKE ? OR d.model LIKE ? OR d.status LIKE ? OR d.type LIKE ? OR v.name LIKE ? "
            "OR s.name LIKE ? OR sv.version LIKE ? OR d.resolution LIKE ? OR d.arch LIKE ? "
            "OR d.cpu LIKE ? OR d.notes LIKE ? OR d.borrower_name LIKE ? "
        )
        params = [
            like,
            like,
            like,
            like,
            like,
            like,
            like,
            like,
            like,
            like,
            like,
            like,
        ]
    sql += "ORDER BY d.id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _fetch_borrow_requests(
    conn,
    query: Optional[str] = None,
    status: Optional[str] = None,
    device_id: Optional[int] = None,
    request_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    sql = (
        "SELECT "
        "br.id, br.device_id, br.device_model, br.borrower_name, br.expected_return_at, "
        "br.request_type, br.status AS request_status, br.requested_at, br.handled_at, "
        "d.status AS device_status, d.type AS device_type, v.name AS vendor_name, "
        "s.name AS system_name, sv.version AS system_version, "
        "d.resolution, d.arch, d.cpu, d.boot_password, d.notes "
        "FROM borrow_requests br "
        "LEFT JOIN devices d ON br.device_id = d.id "
        "LEFT JOIN vendors v ON d.vendor_id = v.id "
        "LEFT JOIN systems s ON d.system_id = s.id "
        "LEFT JOIN system_versions sv ON d.system_version_id = sv.id "
    )
    params: List[Any] = []
    conditions: List[str] = []
    if query:
        like = f"%{query}%"
        conditions.append("(br.borrower_name LIKE ? OR br.device_model LIKE ? OR br.request_type LIKE ?)")
        params.extend([like, like, like])
    if status:
        conditions.append("br.status = ?")
        params.append(status)
    if device_id is not None:
        conditions.append("br.device_id = ?")
        params.append(device_id)
    if request_type:
        conditions.append("br.request_type = ?")
        params.append(request_type)
    if conditions:
        sql += "WHERE " + " AND ".join(conditions) + " "
    sql += "ORDER BY br.requested_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def _fetch_borrow_records(conn, query: Optional[str] = None) -> List[Dict[str, Any]]:
    sql = (
        "SELECT id, device_id, device_model, borrower_name, borrowed_at, expected_return_at, "
        "returned_at, status, request_id "
        "FROM borrow_records "
    )
    params: List[Any] = []
    if query:
        like = f"%{query}%"
        sql += "WHERE borrower_name LIKE ? OR device_model LIKE ? OR status LIKE ? "
        params = [like, like, like]
    sql += "ORDER BY borrowed_at DESC"
    rows = conn.execute(sql, params).fetchall()
    items = [dict(row) for row in rows]
    if not items:
        return items
    record_ids = [item["id"] for item in items if item.get("id") is not None]
    request_ids = [item["request_id"] for item in items if item.get("request_id") is not None]
    if not record_ids and not request_ids:
        return items
    conditions = []
    params: List[Any] = []
    if record_ids:
        placeholders = ",".join("?" for _ in record_ids)
        conditions.append(f"record_id IN ({placeholders})")
        params.extend(record_ids)
    if request_ids:
        placeholders = ",".join("?" for _ in request_ids)
        conditions.append(f"request_id IN ({placeholders})")
        params.extend(request_ids)
    sql = (
        "SELECT id, record_id, request_id, borrower_before, borrower_after, expected_before, "
        "expected_after, changed_at FROM borrow_changes "
    )
    if conditions:
        sql += "WHERE " + " OR ".join(conditions) + " "
    sql += "ORDER BY changed_at ASC"
    change_rows = conn.execute(sql, params).fetchall()
    change_by_record: Dict[int, List[Dict[str, Any]]] = {}
    change_by_request: Dict[int, List[Dict[str, Any]]] = {}
    for row in change_rows:
        data = dict(row)
        if row["record_id"] is not None:
            change_by_record.setdefault(row["record_id"], []).append(data)
        if row["request_id"] is not None:
            change_by_request.setdefault(row["request_id"], []).append(data)
    for item in items:
        record_list = change_by_record.get(item["id"], [])
        request_list = change_by_request.get(item.get("request_id"), [])
        if record_list or request_list:
            item["borrower_changes"] = record_list + [c for c in request_list if c not in record_list]
        else:
            item["borrower_changes"] = []
    return items


def _filter_ai_devices(devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return devices


async def _queue_notify(title: str, body: str):
    webhook = None
    with db_session() as conn:
        webhook = _get_setting(conn, "feishu_webhook")
    if not webhook:
        return
    client: httpx.AsyncClient = app.state.http_client
    try:
        await send_feishu_message(client, webhook, title, body)
    except NotifyError:
        # 避免通知失败影响主流程
        return


async def _overdue_worker():
    while True:
        try:
            await asyncio.sleep(60)
            now = datetime.now(timezone.utc)
            with db_session() as conn:
                rows = conn.execute(
                    "SELECT d.id, d.model, d.borrower_name, d.expected_return_at "
                    "FROM devices d "
                    "WHERE d.loan_status = 'borrowed' AND d.expected_return_at IS NOT NULL AND d.overdue_notified = 0"
                ).fetchall()
                overdue = []
                for row in rows:
                    expected = _parse_datetime(row["expected_return_at"])
                    if expected < now:
                        overdue.append(row)
                if not overdue:
                    continue
                webhook = _get_setting(conn, "feishu_webhook")
                if not webhook:
                    continue
                client: httpx.AsyncClient = app.state.http_client
                for row in overdue:
                    body = (
                        f"借用人名字: {row['borrower_name'] or '-'}\n"
                        f"借用的设备型号: {row['model']}\n"
                        f"预计归还时间: {_format_notify_time(row['expected_return_at'])}\n"
                        "借用时间已逾期"
                    )
                    try:
                        await send_feishu_message(client, webhook, "逾期通知", body)
                    except NotifyError:
                        continue
                    conn.execute(
                        "UPDATE devices SET overdue_notified = 1, updated_at = ? WHERE id = ?",
                        (now_iso(), row["id"]),
                    )
        except asyncio.CancelledError:
            break
        except Exception:
            continue


@app.on_event("startup")
async def on_startup():
    init_db()
    limits = None
    if hasattr(httpx, "Limits"):
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
    if limits:
        app.state.http_client = httpx.AsyncClient(timeout=20.0, limits=limits)
    else:
        app.state.http_client = httpx.AsyncClient(timeout=20.0)
    app.state.overdue_task = asyncio.create_task(_overdue_worker())


@app.on_event("shutdown")
async def on_shutdown():
    task = app.state.overdue_task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await app.state.http_client.aclose()


@app.get("/api/vendors")
async def list_vendors():
    with db_session() as conn:
        rows = conn.execute("SELECT id, name FROM vendors ORDER BY id DESC").fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/vendors")
async def create_vendor(payload: VendorCreate):
    _ensure_required(payload.name, "厂商")
    with db_session() as conn:
        try:
            conn.execute("INSERT INTO vendors (name) VALUES (?)", (payload.name.strip(),))
        except Exception:
            raise HTTPException(status_code=400, detail="厂商已存在")
    return {"message": "新增成功"}


@app.put("/api/vendors/{vendor_id}")
async def update_vendor(vendor_id: int, payload: VendorUpdate):
    _ensure_required(payload.name, "厂商")
    with db_session() as conn:
        try:
            cur = conn.execute("UPDATE vendors SET name = ? WHERE id = ?", (payload.name.strip(), vendor_id))
        except Exception:
            raise HTTPException(status_code=400, detail="厂商名称重复")
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="厂商不存在")
    return {"message": "更新成功"}


@app.delete("/api/vendors/{vendor_id}")
async def delete_vendor(vendor_id: int, payload: VendorDeleteRequest):
    with db_session() as conn:
        existing = conn.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="厂商不存在")
        device_count = conn.execute(
            "SELECT COUNT(1) AS cnt FROM devices WHERE vendor_id = ?",
            (vendor_id,),
        ).fetchone()["cnt"]
        if device_count > 0 and not payload.rebind_vendor_id:
            raise HTTPException(status_code=409, detail="厂商已绑定设备，需要重新绑定")
        if device_count > 0:
            if payload.rebind_vendor_id == vendor_id:
                raise HTTPException(status_code=400, detail="新的厂商不能与原厂商相同")
            target = conn.execute(
                "SELECT id FROM vendors WHERE id = ?",
                (payload.rebind_vendor_id,),
            ).fetchone()
            if not target:
                raise HTTPException(status_code=400, detail="新的厂商不存在")
            conn.execute(
                "UPDATE devices SET vendor_id = ? WHERE vendor_id = ?",
                (payload.rebind_vendor_id, vendor_id),
            )
        conn.execute("DELETE FROM vendors WHERE id = ?", (vendor_id,))
    return {"message": "删除成功"}


@app.get("/api/systems")
async def list_systems(include_versions: bool = Query(False)):
    with db_session() as conn:
        systems = conn.execute("SELECT id, name FROM systems ORDER BY id DESC").fetchall()
        system_list = [dict(row) for row in systems]
        if include_versions:
            versions = conn.execute(
                "SELECT id, system_id, version FROM system_versions ORDER BY id DESC"
            ).fetchall()
            versions_by_system: Dict[int, List[Dict[str, Any]]] = {}
            for row in versions:
                versions_by_system.setdefault(row["system_id"], []).append(dict(row))
            for item in system_list:
                item["versions"] = versions_by_system.get(item["id"], [])
    return {"items": system_list}


@app.post("/api/systems")
async def create_system(payload: SystemCreate):
    _ensure_required(payload.name, "系统")
    with db_session() as conn:
        try:
            conn.execute("INSERT INTO systems (name) VALUES (?)", (payload.name.strip(),))
        except Exception:
            raise HTTPException(status_code=400, detail="系统已存在")
    return {"message": "新增成功"}


@app.put("/api/systems/{system_id}")
async def update_system(system_id: int, payload: SystemUpdate):
    _ensure_required(payload.name, "系统")
    with db_session() as conn:
        try:
            cur = conn.execute("UPDATE systems SET name = ? WHERE id = ?", (payload.name.strip(), system_id))
        except Exception:
            raise HTTPException(status_code=400, detail="系统名称重复")
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="系统不存在")
    return {"message": "更新成功"}


@app.delete("/api/systems/{system_id}")
async def delete_system(system_id: int, payload: SystemDeleteRequest):
    with db_session() as conn:
        existing = conn.execute("SELECT id FROM systems WHERE id = ?", (system_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="系统不存在")
        device_count = conn.execute(
            "SELECT COUNT(1) AS cnt FROM devices WHERE system_id = ?",
            (system_id,),
        ).fetchone()["cnt"]
        if device_count > 0 and (not payload.rebind_system_id or not payload.rebind_version_id):
            raise HTTPException(status_code=409, detail="系统已绑定设备，需要重新绑定")
        if device_count > 0:
            if payload.rebind_system_id == system_id:
                raise HTTPException(status_code=400, detail="新的系统不能与原系统相同")
            target = conn.execute(
                "SELECT id FROM systems WHERE id = ?",
                (payload.rebind_system_id,),
            ).fetchone()
            if not target:
                raise HTTPException(status_code=400, detail="新的系统不存在")
            _validate_version_for_system(conn, payload.rebind_system_id, payload.rebind_version_id)
            conn.execute(
                "UPDATE devices SET system_id = ?, system_version_id = ? WHERE system_id = ?",
                (payload.rebind_system_id, payload.rebind_version_id, system_id),
            )
        conn.execute("DELETE FROM systems WHERE id = ?", (system_id,))
    return {"message": "删除成功"}


@app.post("/api/systems/{system_id}/versions")
async def create_version(system_id: int, payload: VersionCreate):
    _ensure_required(payload.version, "版本")
    with db_session() as conn:
        system = conn.execute("SELECT id FROM systems WHERE id = ?", (system_id,)).fetchone()
        if not system:
            raise HTTPException(status_code=404, detail="系统不存在")
        try:
            conn.execute(
                "INSERT INTO system_versions (system_id, version) VALUES (?, ?)",
                (system_id, payload.version.strip()),
            )
        except Exception:
            raise HTTPException(status_code=400, detail="版本已存在")
    return {"message": "新增成功"}


@app.put("/api/versions/{version_id}")
async def update_version(version_id: int, payload: VersionUpdate):
    _ensure_required(payload.version, "版本")
    with db_session() as conn:
        try:
            cur = conn.execute(
                "UPDATE system_versions SET version = ? WHERE id = ?",
                (payload.version.strip(), version_id),
            )
        except Exception:
            raise HTTPException(status_code=400, detail="版本名称重复")
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="版本不存在")
    return {"message": "更新成功"}


@app.delete("/api/versions/{version_id}")
async def delete_version(version_id: int, payload: VersionDeleteRequest):
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id, system_id FROM system_versions WHERE id = ?", (version_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="版本不存在")
        device_count = conn.execute(
            "SELECT COUNT(1) AS cnt FROM devices WHERE system_version_id = ?",
            (version_id,),
        ).fetchone()["cnt"]
        if device_count > 0 and not payload.rebind_version_id:
            raise HTTPException(status_code=409, detail="版本已绑定设备，需要重新绑定")
        if device_count > 0:
            if payload.rebind_version_id == version_id:
                raise HTTPException(status_code=400, detail="新的版本不能与原版本相同")
            target = conn.execute(
                "SELECT id, system_id FROM system_versions WHERE id = ?",
                (payload.rebind_version_id,),
            ).fetchone()
            if not target:
                raise HTTPException(status_code=400, detail="新的版本不存在")
            if target["system_id"] != existing["system_id"]:
                raise HTTPException(status_code=400, detail="新版本必须属于同一系统")
            conn.execute(
                "UPDATE devices SET system_version_id = ? WHERE system_version_id = ?",
                (payload.rebind_version_id, version_id),
            )
        conn.execute("DELETE FROM system_versions WHERE id = ?", (version_id,))
    return {"message": "删除成功"}


@app.get("/api/devices")
async def list_devices(query: Optional[str] = None):
    with db_session() as conn:
        items = _fetch_devices(conn, query)
    return {"items": items}


@app.post("/api/devices")
async def create_device(payload: DeviceCreate):
    _ensure_required(payload.model, "设备型号")
    _ensure_required(payload.status, "设备状态")
    with db_session() as conn:
        vendor = conn.execute("SELECT id FROM vendors WHERE id = ?", (payload.vendor_id,)).fetchone()
        if not vendor:
            raise HTTPException(status_code=400, detail="厂商不存在")
        system = conn.execute("SELECT id FROM systems WHERE id = ?", (payload.system_id,)).fetchone()
        if not system:
            raise HTTPException(status_code=400, detail="系统不存在")
        _validate_version_for_system(conn, payload.system_id, payload.system_version_id)
        now = now_iso()
        conn.execute(
            """
            INSERT INTO devices (
                model, status, type, vendor_id, system_id, system_version_id,
                resolution, arch, cpu, boot_password, notes,
                loan_status, borrower_name, borrowed_at, expected_return_at,
                overdue_notified, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', NULL, NULL, NULL, 0, ?, ?)
            """,
            (
                payload.model.strip(),
                payload.status.strip(),
                payload.type,
                payload.vendor_id,
                payload.system_id,
                payload.system_version_id,
                payload.resolution,
                payload.arch,
                payload.cpu,
                payload.boot_password,
                payload.notes,
                now,
                now,
            ),
        )
    return {"message": "新增成功"}


@app.put("/api/devices/{device_id}")
async def update_device(device_id: int, payload: DeviceUpdate):
    _ensure_required(payload.model, "设备型号")
    _ensure_required(payload.status, "设备状态")
    with db_session() as conn:
        vendor = conn.execute("SELECT id FROM vendors WHERE id = ?", (payload.vendor_id,)).fetchone()
        if not vendor:
            raise HTTPException(status_code=400, detail="厂商不存在")
        system = conn.execute("SELECT id FROM systems WHERE id = ?", (payload.system_id,)).fetchone()
        if not system:
            raise HTTPException(status_code=400, detail="系统不存在")
        _validate_version_for_system(conn, payload.system_id, payload.system_version_id)
        now = now_iso()
        cur = conn.execute(
            """
            UPDATE devices SET
                model = ?, status = ?, type = ?, vendor_id = ?, system_id = ?, system_version_id = ?,
                resolution = ?, arch = ?, cpu = ?, boot_password = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.model.strip(),
                payload.status.strip(),
                payload.type,
                payload.vendor_id,
                payload.system_id,
                payload.system_version_id,
                payload.resolution,
                payload.arch,
                payload.cpu,
                payload.boot_password,
                payload.notes,
                now,
                device_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="设备不存在")
    return {"message": "更新成功"}


@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: int):
    with db_session() as conn:
        cur = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="设备不存在")
    return {"message": "删除成功"}


@app.post("/api/devices/{device_id}/borrow")
async def borrow_device(device_id: int, payload: BorrowRequest, background_tasks: BackgroundTasks):
    _ensure_required(payload.borrower_name, "借用人名字")
    expected_return = _parse_datetime(payload.expected_return_at)
    now = datetime.now(timezone.utc)
    if expected_return <= now:
        raise HTTPException(status_code=400, detail="预计归还时间必须晚于当前时间")
    with db_session() as conn:
        row = conn.execute(
            "SELECT loan_status, model FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="设备不存在")
        if row["loan_status"] != "available":
            raise HTTPException(status_code=400, detail="设备不可借用")
        request_now = now_iso()
        cur = conn.execute(
            """
            INSERT INTO borrow_requests (
                device_id, device_model, borrower_name, expected_return_at,
                request_type, status, requested_at, handled_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'borrow', 'pending', ?, NULL, ?, ?)
            """,
            (
                device_id,
                row["model"],
                payload.borrower_name.strip(),
                expected_return.isoformat(),
                request_now,
                request_now,
                request_now,
            ),
        )
        conn.execute(
            """
            UPDATE devices SET
                loan_status = 'pending',
                borrower_name = ?,
                borrowed_at = NULL,
                expected_return_at = ?,
                overdue_notified = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (
                payload.borrower_name.strip(),
                expected_return.isoformat(),
                now_iso(),
                device_id,
            ),
        )
    body = (
        f"借用人名字: {payload.borrower_name.strip()}\n"
        f"借用的设备型号: {row['model']}\n"
        f"归还时间: {_format_notify_time(expected_return)}\n"
        "待借设备"
    )
    background_tasks.add_task(_queue_notify, "待借通知", body)
    return {"message": "已提交待借申请", "request_id": cur.lastrowid}


@app.post("/api/devices/{device_id}/extend")
async def extend_device(device_id: int, payload: ExtendRequest, background_tasks: BackgroundTasks):
    expected_return = _parse_datetime(payload.expected_return_at)
    with db_session() as conn:
        row = conn.execute(
            "SELECT loan_status, expected_return_at, borrower_name, model FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="设备不存在")
        if row["loan_status"] != "borrowed":
            raise HTTPException(status_code=400, detail="设备未借出")
        old_expected = _parse_datetime(row["expected_return_at"]) if row["expected_return_at"] else None
        if old_expected and expected_return <= old_expected:
            raise HTTPException(status_code=400, detail="延期时间必须晚于当前预计归还时间")
        conn.execute(
            """
            UPDATE devices SET expected_return_at = ?, overdue_notified = 0, updated_at = ?
            WHERE id = ?
            """,
            (expected_return.isoformat(), now_iso(), device_id),
        )
        _update_borrow_record_expected(conn, device_id, expected_return.isoformat())
    body = (
        f"借用人名字: {row['borrower_name'] or '-'}\n"
        f"借用的设备型号: {row['model']}\n"
        f"预计归还时间(旧): {_format_notify_time(row['expected_return_at'])}\n"
        f"变更为 预计归还时间(新): {_format_notify_time(expected_return)}"
    )
    background_tasks.add_task(_queue_notify, "延期通知", body)
    return {"message": "延期成功"}


@app.post("/api/devices/{device_id}/change-borrower")
async def change_borrower(
    device_id: int, payload: BorrowerChangeRequest, background_tasks: BackgroundTasks
):
    _ensure_required(payload.borrower_name, "借用人名字")
    expected_return = _parse_datetime(payload.expected_return_at)
    now = datetime.now(timezone.utc)
    if expected_return <= now:
        raise HTTPException(status_code=400, detail="预计归还时间必须晚于当前时间")
    with db_session() as conn:
        row = conn.execute(
            "SELECT loan_status, borrower_name, expected_return_at, model FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="设备不存在")
        if row["loan_status"] not in {"borrowed", "pending"}:
            raise HTTPException(status_code=400, detail="设备未处于借用状态")
        if not row["borrower_name"]:
            raise HTTPException(status_code=400, detail="当前设备无借用人")
        pending_change = conn.execute(
            """
            SELECT id FROM borrow_requests
            WHERE device_id = ? AND request_type = 'change' AND status = 'pending'
            LIMIT 1
            """,
            (device_id,),
        ).fetchone()
        if pending_change:
            raise HTTPException(status_code=400, detail="当前设备已有借用人更换申请，需等待管理员处理。")
        old_borrower = row["borrower_name"]
        old_expected = row["expected_return_at"]
        request_now = now_iso()
        conn.execute(
            """
            INSERT INTO borrow_requests (
                device_id, device_model, borrower_name, expected_return_at,
                request_type, status, requested_at, handled_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'change', 'pending', ?, NULL, ?, ?)
            """,
            (
                device_id,
                row["model"],
                payload.borrower_name.strip(),
                expected_return.isoformat(),
                request_now,
                request_now,
                request_now,
            ),
        )
    body = (
        f"设备: {row['model']}\n"
        f"变更前借用人: {old_borrower or '-'}\n"
        f"变更前归还时间: {_format_notify_time(old_expected)}\n"
        f"变更后借用人: {payload.borrower_name.strip()}\n"
        f"变更后预期归还时间: {_format_notify_time(expected_return)}\n"
        f"变更时间: {_format_notify_time(now)}"
    )
    background_tasks.add_task(_queue_notify, "借用人变更通知", body)
    return {"message": "已提交借用人变更申请"}


@app.post("/api/devices/{device_id}/return")
async def return_device(device_id: int, background_tasks: BackgroundTasks):
    now = datetime.now(timezone.utc)
    with db_session() as conn:
        row = conn.execute(
            "SELECT loan_status, borrower_name, model FROM devices WHERE id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="设备不存在")
        if row["loan_status"] != "borrowed":
            raise HTTPException(status_code=400, detail="设备未处于已借出状态")
        conn.execute(
            """
            UPDATE devices SET
                loan_status = 'available',
                borrower_name = NULL,
                borrowed_at = NULL,
                expected_return_at = NULL,
                overdue_notified = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), device_id),
        )
        _close_borrow_record(conn, device_id, now_iso())
    body = (
        f"借用人名字: {row['borrower_name'] or '-'}\n"
        f"借用的设备型号: {row['model']}\n"
        f"归还时间: {_format_notify_time(now)}\n"
        "归还成功"
    )
    background_tasks.add_task(_queue_notify, "归还通知", body)
    return {"message": "归还成功"}


@app.get("/api/borrow-requests")
async def list_borrow_requests(
    query: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    device_id: Optional[int] = Query(default=None),
    request_type: Optional[str] = Query(default=None),
):
    if status and status not in {"pending", "approved", "cancelled"}:
        raise HTTPException(status_code=400, detail="状态参数不合法")
    with db_session() as conn:
        items = _fetch_borrow_requests(conn, query, status, device_id, request_type)
    return {"items": items}


@app.post("/api/borrow-requests/{request_id}/approve")
async def approve_borrow_request(request_id: int, background_tasks: BackgroundTasks):
    now = datetime.now(timezone.utc)
    with db_session() as conn:
        request_row = conn.execute(
            "SELECT * FROM borrow_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        request = _row_to_dict(request_row)
        if not request:
            raise HTTPException(status_code=404, detail="申请不存在")
        if request["status"] != "pending":
            raise HTTPException(status_code=400, detail="申请已处理")
        device = conn.execute(
            "SELECT loan_status, model, borrower_name, expected_return_at FROM devices WHERE id = ?",
            (request["device_id"],),
        ).fetchone()
        if not device:
            raise HTTPException(status_code=404, detail="设备不存在")

        if request["request_type"] == "change":
            if device["loan_status"] not in {"borrowed", "pending"}:
                raise HTTPException(status_code=400, detail="设备状态异常")
            old_borrower = device["borrower_name"]
            old_expected = device["expected_return_at"]
            conn.execute(
                """
                UPDATE devices SET
                    borrower_name = ?,
                    expected_return_at = ?,
                    overdue_notified = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    request["borrower_name"],
                    request["expected_return_at"],
                    now_iso(),
                    request["device_id"],
                ),
            )
            record_row = conn.execute(
                """
                SELECT id FROM borrow_records
                WHERE device_id = ? AND returned_at IS NULL
                ORDER BY borrowed_at DESC
                LIMIT 1
                """,
                (request["device_id"],),
            ).fetchone()
            record_id = record_row["id"] if record_row else None
            change_request_id = request_id
            borrow_request_id = None
            if device["loan_status"] == "pending":
                borrow_request = conn.execute(
                    """
                    SELECT id FROM borrow_requests
                    WHERE device_id = ? AND request_type = 'borrow' AND status = 'pending'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (request["device_id"],),
                ).fetchone()
                if borrow_request:
                    borrow_request_id = borrow_request["id"]
                    conn.execute(
                        """
                        UPDATE borrow_requests
                        SET borrower_name = ?, expected_return_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            request["borrower_name"],
                            request["expected_return_at"],
                            now_iso(),
                            borrow_request_id,
                        ),
                    )
            if record_id:
                conn.execute(
                    """
                    UPDATE borrow_records
                    SET borrower_name = ?, expected_return_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        request["borrower_name"],
                        request["expected_return_at"],
                        now_iso(),
                        record_id,
                    ),
                )
            if record_id or borrow_request_id:
                now_str = now_iso()
                conn.execute(
                    """
                    INSERT INTO borrow_changes (
                        device_id, record_id, request_id, borrower_before, borrower_after,
                        expected_before, expected_after, changed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request["device_id"],
                        record_id,
                        borrow_request_id or change_request_id,
                        old_borrower,
                        request["borrower_name"],
                        old_expected,
                        request["expected_return_at"],
                        now_str,
                        now_str,
                        now_str,
                    ),
                )
            conn.execute(
                """
                UPDATE borrow_requests
                SET status = 'approved', handled_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now_iso(), now_iso(), request_id),
            )
        else:
            if device["loan_status"] != "pending":
                raise HTTPException(status_code=400, detail="设备状态异常")
            borrowed_at = now_iso()
            conn.execute(
                """
                UPDATE devices SET
                    loan_status = 'borrowed',
                    borrower_name = ?,
                    borrowed_at = ?,
                    expected_return_at = ?,
                    overdue_notified = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    request["borrower_name"],
                    borrowed_at,
                    request["expected_return_at"],
                    now_iso(),
                    request["device_id"],
                ),
            )
            conn.execute(
                """
                UPDATE borrow_requests
                SET status = 'approved', handled_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (borrowed_at, now_iso(), request_id),
            )
            _insert_borrow_record(
                conn,
                request["device_id"],
                request["device_model"],
                request["borrower_name"],
                borrowed_at,
                request["expected_return_at"],
                request_id,
            )

    if request["request_type"] == "change":
        body = (
            f"设备: {request['device_model']}\n"
            f"新的借用人名字: {request['borrower_name']}\n"
            f"新的归还时间: {_format_notify_time(request['expected_return_at'])}"
        )
        background_tasks.add_task(_queue_notify, "借用人变更成功通知", body)
        return {"message": "借用人变更成功"}

    body = (
        f"借用人名字: {request['borrower_name']}\n"
        f"借用的设备型号: {request['device_model']}\n"
        f"借用时间: {_format_notify_time(now)}\n"
        f"预计归还时间: {_format_notify_time(request['expected_return_at'])}\n"
        "借用成功"
    )
    background_tasks.add_task(_queue_notify, "借用通知", body)
    return {"message": "确认借出成功"}


@app.post("/api/borrow-requests/{request_id}/cancel")
async def cancel_borrow_request(request_id: int):
    now = now_iso()
    with db_session() as conn:
        request = conn.execute(
            "SELECT * FROM borrow_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="申请不存在")
        if request["status"] != "pending":
            raise HTTPException(status_code=400, detail="申请已处理")
        conn.execute(
            """
            UPDATE borrow_requests
            SET status = 'cancelled', handled_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now_iso(), request_id),
        )
        if request["request_type"] != "change":
            conn.execute(
                """
                UPDATE devices SET
                    loan_status = 'available',
                    borrower_name = NULL,
                    borrowed_at = NULL,
                    expected_return_at = NULL,
                    overdue_notified = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                (now_iso(), request["device_id"]),
            )
    return {"message": "取消成功"}


@app.get("/api/borrow-records")
async def list_borrow_records(query: Optional[str] = Query(default=None)):
    with db_session() as conn:
        items = _fetch_borrow_records(conn, query)
    return {"items": items}


@app.get("/api/settings/feishu")
async def get_feishu_setting():
    with db_session() as conn:
        webhook = _get_setting(conn, "feishu_webhook")
    return {"webhook_url": webhook}


@app.put("/api/settings/feishu")
async def update_feishu_setting(payload: SettingUpdate):
    _ensure_required(payload.webhook_url, "Webhook")
    with db_session() as conn:
        _set_setting(conn, "feishu_webhook", payload.webhook_url.strip())
    return {"message": "保存成功"}


@app.get("/api/llm/models")
async def list_llm_models():
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id, name, api_type, base_url, api_key, model, max_tokens, is_default FROM llm_models ORDER BY id DESC"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/llm/models/assignments")
async def get_llm_assignments():
    with db_session() as conn:
        fast_id = _get_int_setting(conn, "llm_fast_model_id")
        accurate_id = _get_int_setting(conn, "llm_accurate_model_id")
    return {"fast_model_id": fast_id, "accurate_model_id": accurate_id}


def _reset_default(conn):
    conn.execute("UPDATE llm_models SET is_default = 0")


def _ensure_default(conn):
    row = conn.execute("SELECT id FROM llm_models WHERE is_default = 1 ORDER BY id LIMIT 1").fetchone()
    if not row:
        first = conn.execute("SELECT id FROM llm_models ORDER BY id LIMIT 1").fetchone()
        if first:
            conn.execute("UPDATE llm_models SET is_default = 1 WHERE id = ?", (first["id"],))


@app.post("/api/llm/models")
async def create_llm_model(payload: LLMModelCreate):
    with db_session() as conn:
        now = now_iso()
        if payload.is_default:
            _reset_default(conn)
        conn.execute(
            """
            INSERT INTO llm_models (name, api_type, base_url, api_key, model, max_tokens, is_default, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.name.strip(),
                payload.api_type.strip(),
                payload.base_url.strip(),
                payload.api_key.strip(),
                payload.model.strip(),
                payload.max_tokens,
                1 if payload.is_default else 0,
                now,
                now,
            ),
        )
        _ensure_default(conn)
    return {"message": "新增成功"}


@app.post("/api/llm/models/{model_id}/assign")
async def assign_llm_model(model_id: int, payload: LLMModelAssignRequest):
    with db_session() as conn:
        _assign_llm_model(conn, model_id, payload.role)
    return {"message": "指派成功"}


@app.delete("/api/llm/models/assignments/{role}")
async def clear_llm_assignment(role: str):
    with db_session() as conn:
        _clear_llm_assignment(conn, role)
    return {"message": "取消指派成功"}


@app.put("/api/llm/models/{model_id}")
async def update_llm_model(model_id: int, payload: LLMModelUpdate):
    with db_session() as conn:
        if payload.is_default:
            _reset_default(conn)
        cur = conn.execute(
            """
            UPDATE llm_models SET
                name = ?, api_type = ?, base_url = ?, api_key = ?, model = ?, max_tokens = ?, is_default = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                payload.name.strip(),
                payload.api_type.strip(),
                payload.base_url.strip(),
                payload.api_key.strip(),
                payload.model.strip(),
                payload.max_tokens,
                1 if payload.is_default else 0,
                now_iso(),
                model_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="模型不存在")
        _ensure_default(conn)
    return {"message": "更新成功"}


@app.delete("/api/llm/models/{model_id}")
async def delete_llm_model(model_id: int):
    with db_session() as conn:
        cur = conn.execute("DELETE FROM llm_models WHERE id = ?", (model_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="模型不存在")
        _ensure_default(conn)
    return {"message": "删除成功"}


@app.post("/api/llm/models/{model_id}/test")
async def test_llm_model(model_id: int):
    with db_session() as conn:
        row = conn.execute("SELECT * FROM llm_models WHERE id = ?", (model_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="模型不存在")
        config = dict(row)
    client: httpx.AsyncClient = app.state.http_client
    try:
        await call_llm(
            client,
            config,
            "你是一个测试助手。",
            "请返回 JSON: {\"device_ids\": []}",
        )
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=f"模型不可用: {exc}")
    return {"message": "模型可用"}


@app.post("/api/llm/search")
async def ai_search(payload: Dict[str, Any]):
    query = str(payload.get("query", "")).strip()
    if not query:
        raise HTTPException(status_code=400, detail="请输入搜索内容")
    mode = str(payload.get("mode", "")).strip().lower()
    with db_session() as conn:
        row = conn.execute("SELECT * FROM llm_models WHERE is_default = 1 ORDER BY id LIMIT 1").fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="AI 模型服务暂不可用")
        config = dict(row)
        if mode in ("fast", "accurate"):
            fast_id = _get_int_setting(conn, "llm_fast_model_id")
            accurate_id = _get_int_setting(conn, "llm_accurate_model_id")
            selected_id = fast_id if mode == "fast" else accurate_id
            if selected_id:
                selected_row = conn.execute(
                    "SELECT * FROM llm_models WHERE id = ?",
                    (selected_id,),
                ).fetchone()
                if selected_row:
                    config = dict(selected_row)
        devices = _fetch_devices(conn)
    ai_candidates = _filter_ai_devices(devices)
    device_payload = [
        {
            "id": item["id"],
            "model": item["model"],
            "type": item["type"],
            "vendor": item["vendor_name"],
            "system": item["system_name"],
            "version": item["system_version"],
            "status": item["status"],
            "resolution": item["resolution"],
            "arch": item["arch"],
            "cpu": item["cpu"],
            "boot_password": item["boot_password"],
            "notes": item["notes"],
            "loan_status": item["loan_status"],
            "borrower_name": item["borrower_name"],
            "borrowed_at": item["borrowed_at"],
            "expected_return_at": item["expected_return_at"],
        }
        for item in ai_candidates
    ]
    system_prompt = (
        "你是设备匹配助手。根据用户需求，从设备列表中挑选最合适的设备 ID。"
        "仅返回 JSON，不要输出多余文字或代码块。"
        "返回 JSON 格式：{\"device_ids\":[1,2],\"reason\":\"...\"}"
    )
    user_prompt = f"用户需求: {query}\n设备列表: {json.dumps(device_payload, ensure_ascii=False)}"
    client: httpx.AsyncClient = app.state.http_client
    try:
        result = await call_llm(client, config, system_prompt, user_prompt)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=f"AI 模型服务暂不可用: {exc}")
    device_ids = result.get("device_ids") or []
    if not isinstance(device_ids, list):
        device_ids = []
    matched = [item for item in ai_candidates if item["id"] in device_ids]
    return {"items": matched, "ai_reason": result.get("reason", "")}
