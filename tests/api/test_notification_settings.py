import os
from pathlib import Path

import httpx
import pytest

from backend import main
from backend.db import init_db
from backend.notify import DEFAULT_BORROW_ADMIN_URL, build_feishu_card_payload


@pytest.fixture()
def notification_db():
    os.environ["APP_DB_FILE"] = "data/apitest.db"
    db_path = Path(__file__).resolve().parents[2] / "data" / "apitest.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    yield


@pytest.mark.asyncio
async def test_notification_settings_save_and_apply_to_payload(notification_db):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/settings/notifications")
        assert response.status_code == 200
        items = response.json()["items"]
        payload = {"settings": {item["key"]: dict(item["params"]) for item in items}}
        payload["settings"]["borrow_approve"]["card_title"] = "借用确认已完成"
        payload["settings"]["borrow_approve"]["status"] = "请到管理员处领取设备"

        save_response = await client.put("/api/settings/notifications", json=payload)
        assert save_response.status_code == 200
        saved = next(item for item in save_response.json()["items"] if item["key"] == "borrow_approve")
        assert saved["params"]["card_title"] == "借用确认已完成"
        assert saved["params"]["status"] == "请到管理员处领取设备"
        assert saved["customized"] is True

    merged = main._build_configured_portal_card_payload(
        trigger="borrow_approve",
        borrower="Alice",
        device_name="Phone",
        request_date="2099-01-01T00:00:00+00:00",
        return_date="2099-01-02T00:00:00+00:00",
    )
    assert merged["card_title"] == "借用确认已完成"
    assert merged["status"] == "请到管理员处领取设备"


@pytest.mark.asyncio
async def test_notification_settings_render_change_placeholders(notification_db):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/settings/notifications")
        items = response.json()["items"]
        payload = {"settings": {item["key"]: dict(item["params"]) for item in items}}
        payload["settings"]["change_borrower_submit_new"]["status"] = "{old_borrower} -> {new_borrower}"
        save_response = await client.put("/api/settings/notifications", json=payload)
        assert save_response.status_code == 200

    merged = main._build_configured_portal_card_payload(
        trigger="change_borrower_submit_new",
        borrower="Bob",
        device_name="Phone",
        request_date="2099-01-01T00:00:00+00:00",
        return_date="2099-01-02T00:00:00+00:00",
        template_values={"old_borrower": "Alice", "new_borrower": "Bob"},
    )
    assert merged["status"] == "Alice -> Bob"


@pytest.mark.asyncio
async def test_webhook_notification_settings_save_admin_link_and_colors(notification_db):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        feishu_response = await client.get("/api/settings/feishu")
        assert feishu_response.status_code == 200
        assert feishu_response.json()["admin_url"] == DEFAULT_BORROW_ADMIN_URL

        response = await client.get("/api/settings/webhook-notifications")
        assert response.status_code == 200
        items = response.json()["items"]
        by_key = {item["key"]: item for item in items}
        assert by_key["borrow_submit"]["params"]["card_color"] == "blue"
        assert by_key["borrow_submit"]["params"]["card_title"] == "待借通知"
        assert "借用人名字: {borrower}" in by_key["borrow_submit"]["params"]["body_template"]
        assert by_key["borrow_cancel"]["params"]["card_color"] == "red"
        assert by_key["borrow_approve"]["params"]["card_color"] == "green"
        assert by_key["overdue"]["params"]["card_color"] == "red"

        payload = {"settings": {item["key"]: dict(item["params"]) for item in items}}
        payload["settings"]["borrow_submit"]["card_color"] = "green"
        payload["settings"]["borrow_submit"]["card_title"] = "待借确认提醒"
        payload["settings"]["borrow_submit"]["body_template"] = "申请人: {borrower}\n设备: {device_model}\n入口已配置"
        save_response = await client.put("/api/settings/webhook-notifications", json=payload)
        assert save_response.status_code == 200
        saved = next(item for item in save_response.json()["items"] if item["key"] == "borrow_submit")
        assert saved["params"]["card_color"] == "green"
        assert saved["params"]["card_title"] == "待借确认提醒"
        assert saved["params"]["body_template"] == "申请人: {borrower}\n设备: {device_model}\n入口已配置"
        assert saved["customized"] is True

    with main.db_session() as conn:
        configured = main._build_configured_webhook_message(
            conn,
            trigger="borrow_submit",
            fallback_title="待借通知",
            fallback_body="",
            template_values={"borrower": "Alice", "device_model": "Phone"},
        )
    assert configured["title"] == "待借确认提醒"
    assert configured["body"] == "申请人: Alice\n设备: Phone\n入口已配置"
    assert configured["card_color"] == "green"

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        feishu_save = await client.put(
            "/api/settings/feishu",
            json={"webhook_url": "http://webhook.test", "admin_url": "http://admin.test/admin"},
        )
        assert feishu_save.status_code == 200
        assert (await client.get("/api/settings/feishu")).json()["admin_url"] == "http://admin.test/admin"


def test_build_feishu_card_payload_keeps_body_fields_and_admin_link():
    payload = build_feishu_card_payload(
        "待借通知",
        "借用人名字: Alice\n借用的设备型号: Phone\n待借设备",
        card_color="blue",
        admin_url="http://admin.test/admin",
    )

    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["template"] == "blue"
    fields = payload["card"]["elements"][0]["fields"]
    contents = [field["text"]["content"] for field in fields]
    assert "**借用人名字:** Alice" in contents
    assert "**借用的设备型号:** Phone" in contents
    assert "待借设备" in contents
    assert "**设备借用管理页:** [点击查看](http://admin.test/admin)" in contents
