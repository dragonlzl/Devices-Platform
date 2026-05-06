import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.db import db_session, init_db, now_iso
from backend.notify import (
    PORTAL_NOTIFICATION_TEMPLATE_ID,
    PORTAL_NOTIFICATION_TEMPLATE_VERSION,
    PortalNotificationError,
    send_portal_notification,
)


class DummyPortalResponse:
    def __init__(self, status_code, payload, reason_phrase="OK"):
        self.status_code = status_code
        self._payload = payload
        self.reason_phrase = reason_phrase

    def json(self):
        return self._payload


class DummyPortalClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers or {}, "json": json})
        return self.response


@pytest.fixture()
def client(monkeypatch):
    os.environ["APP_DB_FILE"] = "data/apitest.db"
    os.environ.pop("PORTAL_NOTIFICATION_SERVICE_ID", None)
    os.environ.pop("PORTAL_NOTIFICATION_SERVICE_TOKEN", None)
    db_path = Path(__file__).resolve().parents[2] / "data" / "apitest.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    with TestClient(main.app) as test_client:
        yield test_client
    os.environ.pop("PORTAL_NOTIFICATION_SERVICE_ID", None)
    os.environ.pop("PORTAL_NOTIFICATION_SERVICE_TOKEN", None)


def create_vendor_system_version(client):
    client.post("/api/vendors", json={"name": "Apple"})
    system = client.post("/api/systems", json={"name": "iOS"})
    assert system.status_code == 200
    system_id = client.get("/api/systems?include_versions=1").json()["items"][0]["id"]
    client.post(f"/api/systems/{system_id}/versions", json={"version": "17.0"})
    vendor_id = client.get("/api/vendors").json()["items"][0]["id"]
    version_id = client.get("/api/systems?include_versions=1").json()["items"][0]["versions"][0]["id"]
    return vendor_id, system_id, version_id


@pytest.mark.asyncio
async def test_send_portal_notification_builds_jwt_request():
    portal_client = DummyPortalClient(DummyPortalResponse(200, {"success": True, "code": "OK"}))

    result = await send_portal_notification(
        portal_client,
        recipient_user_id="ou_alice",
        portal_jwt="jwt-value",
        payload={"borrower": "Alice", "device_name": "iPhone"},
    )

    assert result["success"] is True
    call = portal_client.calls[0]
    assert call["headers"]["Authorization"] == "Bearer jwt-value"
    assert "Cookie" not in call["headers"]
    assert call["json"]["recipient_user_id"] == "ou_alice"
    assert call["json"]["template_id"] == PORTAL_NOTIFICATION_TEMPLATE_ID
    assert call["json"]["template_version_name"] == PORTAL_NOTIFICATION_TEMPLATE_VERSION
    assert call["json"]["template_variable"] == {}
    assert call["json"]["payload"]["device_name"] == "iPhone"


@pytest.mark.asyncio
async def test_send_portal_notification_builds_service_account_request():
    portal_client = DummyPortalClient(DummyPortalResponse(200, {"success": True, "code": "OK"}))

    await send_portal_notification(
        portal_client,
        recipient_user_id="ou_alice",
        service_id="device-borrow-service",
        service_token="service-secret",
        payload={"borrower": "Alice", "device_name": "iPhone"},
    )

    call = portal_client.calls[0]
    assert call["headers"]["X-Portal-Service-Id"] == "device-borrow-service"
    assert call["headers"]["Authorization"] == "Bearer service-secret"
    assert "Cookie" not in call["headers"]
    assert call["json"]["template_variable"] == {}
    assert call["json"]["payload"]["device_name"] == "iPhone"


@pytest.mark.asyncio
async def test_send_portal_notification_rejects_invalid_body():
    portal_client = DummyPortalClient(DummyPortalResponse(200, {"success": True}))

    with pytest.raises(PortalNotificationError) as missing_recipient:
        await send_portal_notification(
            portal_client,
            recipient_user_id="",
            portal_jwt="jwt-value",
            payload={"borrower": "Alice"},
        )
    assert missing_recipient.value.status_code == 400

    with pytest.raises(PortalNotificationError) as invalid_payload:
        await send_portal_notification(
            portal_client,
            recipient_user_id="ou_alice",
            portal_jwt="jwt-value",
            payload=[],  # type: ignore[arg-type]
        )
    assert invalid_payload.value.status_code == 400


@pytest.mark.asyncio
async def test_send_portal_notification_handles_401_and_success_false_without_secret():
    token = "secret-token"
    portal_client = DummyPortalClient(
        DummyPortalResponse(
            401,
            {
                "success": False,
                "code": "NOTIFICATION_JWT_INVALID",
                "message": f"Authorization: Bearer {token} expired",
            },
            reason_phrase="Unauthorized",
        )
    )

    with pytest.raises(PortalNotificationError) as exc:
        await send_portal_notification(
            portal_client,
            recipient_user_id="ou_alice",
            portal_jwt=token,
            payload={"borrower": "Alice"},
        )
    assert exc.value.status_code == 401
    assert exc.value.code == "NOTIFICATION_JWT_INVALID"
    assert token not in exc.value.message

    failing_client = DummyPortalClient(
        DummyPortalResponse(200, {"success": False, "code": "NOTIFICATION_SEND_FAILED", "message": "failed"})
    )
    with pytest.raises(PortalNotificationError) as failed:
        await send_portal_notification(
            failing_client,
            recipient_user_id="ou_alice",
            portal_jwt="jwt-value",
            payload={"borrower": "Alice"},
        )
    assert failed.value.status_code == 200
    assert failed.value.code == "NOTIFICATION_SEND_FAILED"


def test_borrow_notification_failure_does_not_block_flow(client, monkeypatch):
    calls = []

    async def fake_profile(request):
        return {
            "name": "Alice",
            "user_id": "ou_alice",
            "open_id": None,
            "avatar_url": None,
            "job_title": None,
        }

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        raise PortalNotificationError("login expired", status_code=401, code="NOTIFICATION_JWT_INVALID")

    monkeypatch.setattr(main, "_require_portal_borrower_profile", fake_profile)
    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.post(
        "/api/devices",
        json={
            "model": "PortalPhone",
            "status": "正常",
            "type": "手机",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    device_id = client.get("/api/devices").json()["items"][0]["id"]
    response = client.post(
        f"/api/devices/{device_id}/borrow",
        headers={"X-Portal-JWT": "request-jwt"},
        json={"borrower_name": "Alice", "expected_return_at": "2099-12-31T10:00:00+00:00"},
    )

    assert response.status_code == 200
    assert calls[0]["recipient_user_id"] == "ou_alice"
    assert calls[0]["portal_jwt"] == "request-jwt"
    assert calls[0]["payload"]["card_title"] == "借用申请已提交"
    assert calls[0]["payload"]["status"] == "待管理员确认设备状态"


def test_legacy_webhook_failure_does_not_skip_portal_notification(client, monkeypatch):
    calls = []

    async def fake_profile(request):
        return {
            "name": "Alice",
            "user_id": "ou_alice",
            "open_id": None,
            "avatar_url": None,
            "job_title": None,
        }

    async def broken_legacy_notify(*args, **kwargs):
        raise RuntimeError("legacy webhook unavailable")

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "code": "OK"}

    monkeypatch.setattr(main, "_require_portal_borrower_profile", fake_profile)
    monkeypatch.setattr(main, "send_feishu_message", broken_legacy_notify)
    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.put("/api/settings/feishu", json={"webhook_url": "http://127.0.0.1:1/broken"})
    client.post(
        "/api/devices",
        json={
            "model": "LegacyFailurePhone",
            "status": "正常",
            "type": "手机",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    device_id = client.get("/api/devices").json()["items"][0]["id"]

    response = client.post(
        f"/api/devices/{device_id}/borrow",
        headers={"X-Portal-JWT": "request-jwt"},
        json={"borrower_name": "Alice", "expected_return_at": "2099-12-31T10:00:00+00:00"},
    )

    assert response.status_code == 200
    assert calls
    assert calls[0]["recipient_user_id"] == "ou_alice"
    assert calls[0]["payload"]["card_title"] == "借用申请已提交"


def test_cancel_and_change_notifications_use_expected_recipients(client, monkeypatch):
    calls = []
    current_profile = {
        "name": "Alice",
        "user_id": "ou_alice",
        "open_id": None,
        "avatar_url": None,
        "job_title": None,
    }

    async def fake_profile(request):
        return current_profile

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "code": "OK"}

    monkeypatch.setattr(main, "_require_portal_borrower_profile", fake_profile)
    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.post(
        "/api/devices",
        json={
            "model": "ChangePortalPhone",
            "status": "正常",
            "type": "手机",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    device_id = client.get("/api/devices").json()["items"][0]["id"]
    client.post(
        f"/api/devices/{device_id}/borrow",
        headers={"X-Portal-JWT": "alice-jwt"},
        json={"borrower_name": "Alice", "expected_return_at": "2099-12-31T10:00:00+00:00"},
    )
    borrow_request = client.get("/api/borrow-requests?status=pending").json()["items"][0]
    calls.clear()

    cancel = client.post(
        f"/api/borrow-requests/{borrow_request['id']}/cancel",
        headers={"X-Portal-JWT": "admin-jwt"},
    )
    assert cancel.status_code == 200
    assert calls[0]["recipient_user_id"] == "ou_alice"
    assert calls[0]["payload"]["card_title"] == "借用失败"
    assert calls[0]["payload"]["card_color"] == "red"

    client.post(
        f"/api/devices/{device_id}/borrow",
        headers={"X-Portal-JWT": "alice-jwt"},
        json={"borrower_name": "Alice", "expected_return_at": "2099-12-31T10:00:00+00:00"},
    )
    request_id = client.get("/api/borrow-requests?status=pending").json()["items"][0]["id"]
    client.post(f"/api/borrow-requests/{request_id}/approve", headers={"X-Portal-JWT": "admin-jwt"})

    current_profile = {
        "name": "Bob",
        "user_id": "ou_bob",
        "open_id": None,
        "avatar_url": None,
        "job_title": None,
    }
    calls.clear()
    change = client.post(
        f"/api/devices/{device_id}/change-borrower",
        headers={"X-Portal-JWT": "bob-jwt"},
        json={"borrower_name": "Bob", "expected_return_at": "2099-12-31T12:00:00+00:00"},
    )
    assert change.status_code == 200
    assert [item["recipient_user_id"] for item in calls] == ["ou_alice", "ou_bob"]
    assert {item["payload"]["card_title"] for item in calls} == {"借用人变更申请"}
    assert calls[0]["payload"]["status"] == "待管理员确认，借用人将变为Bob"
    assert calls[1]["payload"]["status"] == "待管理员确认，Alice将变为Bob"

    change_request = next(
        item for item in client.get("/api/borrow-requests?status=pending").json()["items"] if item["request_type"] == "change"
    )
    calls.clear()
    approve_change = client.post(
        f"/api/borrow-requests/{change_request['id']}/approve",
        headers={"X-Portal-JWT": "admin-jwt"},
    )
    assert approve_change.status_code == 200
    assert [item["recipient_user_id"] for item in calls] == ["ou_alice", "ou_bob"]
    assert {item["payload"]["card_title"] for item in calls} == {"借用人变更成功"}


def _seed_overdue_device(status="正常"):
    now = now_iso()
    overdue_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    with db_session() as conn:
        conn.execute("INSERT INTO vendors (name) VALUES ('Apple')")
        vendor_id = conn.execute("SELECT id FROM vendors").fetchone()["id"]
        conn.execute("INSERT INTO systems (name) VALUES ('iOS')")
        system_id = conn.execute("SELECT id FROM systems").fetchone()["id"]
        conn.execute(
            "INSERT INTO system_versions (system_id, version) VALUES (?, '17.0')",
            (system_id,),
        )
        version_id = conn.execute("SELECT id FROM system_versions").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO devices (
                model, status, type, vendor_id, system_id, system_version_id,
                loan_status, borrower_name, borrower_user_id, borrowed_at, expected_return_at,
                overdue_notified, created_at, updated_at
            ) VALUES ('OverduePhone', ?, '手机', ?, ?, ?, 'borrowed',
                      'Alice', 'ou_alice', ?, ?, 0, ?, ?)
            """,
            (status, vendor_id, system_id, version_id, now, overdue_at, now, now),
        )
        device_id = conn.execute("SELECT id FROM devices").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO borrow_requests (
                device_id, device_model, borrower_name, borrower_user_id, expected_return_at,
                request_type, status, requested_at, handled_at, created_at, updated_at
            ) VALUES (?, 'OverduePhone', 'Alice', 'ou_alice', ?, 'borrow', 'approved', ?, ?, ?, ?)
            """,
            (device_id, overdue_at, now, now, now, now),
        )
        request_id = conn.execute("SELECT id FROM borrow_requests").fetchone()["id"]
        conn.execute(
            """
            INSERT INTO borrow_records (
                device_id, device_model, borrower_name, borrower_user_id, borrowed_at,
                expected_return_at, returned_at, status, request_id, created_at, updated_at
            ) VALUES (?, 'OverduePhone', 'Alice', 'ou_alice', ?, ?, NULL, 'borrowed', ?, ?, ?)
            """,
            (device_id, now, overdue_at, request_id, now, now),
        )
    return device_id, overdue_at


def test_overdue_notification_waits_for_service_credentials_then_sends(client, monkeypatch):
    calls = []
    _seed_overdue_device()

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "code": "OK"}

    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))
    assert calls == []
    with db_session() as conn:
        pending = conn.execute("SELECT status, last_error_code FROM overdue_notifications").fetchone()
        device = conn.execute("SELECT overdue_notified FROM devices").fetchone()
    assert pending["status"] == "pending"
    assert pending["last_error_code"] == "NOTIFICATION_AUTH_REQUIRED"
    assert device["overdue_notified"] == 0

    os.environ["PORTAL_NOTIFICATION_SERVICE_ID"] = "device-borrow-service"
    os.environ["PORTAL_NOTIFICATION_SERVICE_TOKEN"] = "service-token"
    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))
    with db_session() as conn:
        sent = conn.execute("SELECT status, sent_at FROM overdue_notifications").fetchone()
        device = conn.execute("SELECT overdue_notified FROM devices").fetchone()
    assert calls[0].get("portal_jwt") is None
    assert calls[0]["service_id"] == "device-borrow-service"
    assert calls[0]["service_token"] == "service-token"
    assert calls[0]["recipient_user_id"] == "ou_alice"
    assert calls[0]["payload"]["card_title"] == "设备借用逾期"
    assert sent["status"] == "sent"
    assert sent["sent_at"] is not None
    assert device["overdue_notified"] == 1


def test_overdue_notification_keeps_legacy_webhook_when_portal_auth_missing(client, monkeypatch):
    portal_calls = []
    webhook_calls = []
    _seed_overdue_device()
    with db_session() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('feishu_webhook', 'http://webhook.test')")

    async def fake_portal_send(*args, **kwargs):
        portal_calls.append(kwargs)
        return {"success": True, "code": "OK"}

    async def fake_webhook_send(*args, **kwargs):
        webhook_calls.append({"title": args[2], "body": args[3]})

    monkeypatch.setattr(main, "send_portal_notification", fake_portal_send)
    monkeypatch.setattr(main, "send_feishu_message", fake_webhook_send)

    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))
    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))

    with db_session() as conn:
        pending = conn.execute(
            "SELECT status, last_error_code, webhook_sent_at FROM overdue_notifications"
        ).fetchone()
        device = conn.execute("SELECT overdue_notified FROM devices").fetchone()
    assert portal_calls == []
    assert len(webhook_calls) == 1
    assert webhook_calls[0]["title"] == "逾期通知"
    assert "借用时间已逾期" in webhook_calls[0]["body"]
    assert pending["status"] == "pending"
    assert pending["last_error_code"] == "NOTIFICATION_AUTH_REQUIRED"
    assert pending["webhook_sent_at"] is not None
    assert device["overdue_notified"] == 1


def test_overdue_webhook_failure_does_not_block_portal_notification(client, monkeypatch):
    portal_calls = []
    _seed_overdue_device()
    os.environ["PORTAL_NOTIFICATION_SERVICE_TOKEN"] = "service-token"
    with db_session() as conn:
        conn.execute("INSERT INTO settings (key, value) VALUES ('feishu_webhook', 'http://webhook.test')")

    async def fake_portal_send(*args, **kwargs):
        portal_calls.append(kwargs)
        return {"success": True, "code": "OK"}

    async def broken_webhook(*args, **kwargs):
        raise RuntimeError("webhook failed")

    monkeypatch.setattr(main, "send_portal_notification", fake_portal_send)
    monkeypatch.setattr(main, "send_feishu_message", broken_webhook)

    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))

    with db_session() as conn:
        sent = conn.execute(
            "SELECT status, sent_at, webhook_sent_at, webhook_last_error_message FROM overdue_notifications"
        ).fetchone()
    assert portal_calls[0].get("portal_jwt") is None
    assert portal_calls[0]["service_id"] == "device-borrow-service"
    assert portal_calls[0]["service_token"] == "service-token"
    assert sent["status"] == "sent"
    assert sent["sent_at"] is not None
    assert sent["webhook_sent_at"] is None
    assert "webhook failed" in sent["webhook_last_error_message"]


def test_overdue_notification_handles_invalid_service_token_without_leaking_secret(client, monkeypatch):
    calls = []
    _seed_overdue_device()
    os.environ["PORTAL_NOTIFICATION_SERVICE_TOKEN"] = "invalid-service-token"

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        raise PortalNotificationError(
            "Authorization: Bearer invalid-service-token rejected",
            status_code=401,
            code="NOTIFICATION_SERVICE_TOKEN_INVALID",
        )

    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))

    with db_session() as conn:
        pending = conn.execute(
            "SELECT status, last_error_code, last_error_message, last_error_status FROM overdue_notifications"
        ).fetchone()
    assert calls[0].get("portal_jwt") is None
    assert calls[0]["service_id"] == "device-borrow-service"
    assert calls[0]["service_token"] == "invalid-service-token"
    assert calls[0]["recipient_user_id"] == "ou_alice"
    assert pending["status"] == "pending"
    assert pending["last_error_code"] == "NOTIFICATION_SERVICE_TOKEN_INVALID"
    assert pending["last_error_status"] == 401
    assert "invalid-service-token" not in pending["last_error_message"]
    assert pending["status"] == "pending"


def test_overdue_notification_does_not_queue_resident_device(client, monkeypatch):
    calls = []
    _seed_overdue_device(status="被常驻")
    os.environ["PORTAL_NOTIFICATION_SERVICE_TOKEN"] = "service-token"

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "code": "OK"}

    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))

    with db_session() as conn:
        notification_count = conn.execute("SELECT COUNT(1) AS count FROM overdue_notifications").fetchone()["count"]
        device = conn.execute("SELECT overdue_notified FROM devices").fetchone()
    assert calls == []
    assert notification_count == 0
    assert device["overdue_notified"] == 0


def test_overdue_notification_skips_if_device_becomes_resident_before_send(client, monkeypatch):
    calls = []
    device_id, _ = _seed_overdue_device()
    checked_at = datetime.now(timezone.utc)
    os.environ["PORTAL_NOTIFICATION_SERVICE_TOKEN"] = "service-token"

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "code": "OK"}

    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    with db_session() as conn:
        main._upsert_pending_overdue_notifications(conn, checked_at)
        conn.execute(
            "UPDATE devices SET status = ?, updated_at = ? WHERE id = ?",
            ("被常驻", now_iso(), device_id),
        )

    asyncio.run(main._process_overdue_notifications_once(checked_at))

    with db_session() as conn:
        skipped = conn.execute("SELECT status, last_error_code FROM overdue_notifications").fetchone()
        device = conn.execute("SELECT overdue_notified FROM devices WHERE id = ?", (device_id,)).fetchone()
    assert calls == []
    assert skipped["status"] == "skipped"
    assert skipped["last_error_code"] == "OVERDUE_NOTIFICATION_STALE"
    assert device["overdue_notified"] == 0


def test_overdue_notification_skips_stale_snapshot_after_return_time_changes(client, monkeypatch):
    calls = []
    device_id, _ = _seed_overdue_device()

    async def fake_send(*args, **kwargs):
        calls.append(kwargs)
        return {"success": True, "code": "OK"}

    monkeypatch.setattr(main, "send_portal_notification", fake_send)

    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))
    future_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with db_session() as conn:
        conn.execute(
            "UPDATE devices SET expected_return_at = ?, overdue_notified = 0, updated_at = ? WHERE id = ?",
            (future_at, now_iso(), device_id),
        )
    os.environ["PORTAL_NOTIFICATION_SERVICE_TOKEN"] = "service-token"
    asyncio.run(main._process_overdue_notifications_once(datetime.now(timezone.utc)))

    with db_session() as conn:
        skipped = conn.execute("SELECT status, last_error_code FROM overdue_notifications").fetchone()
    assert calls == []
    assert skipped["status"] == "skipped"
    assert skipped["last_error_code"] == "OVERDUE_NOTIFICATION_STALE"
