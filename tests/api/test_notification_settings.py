import os
from pathlib import Path

import httpx
import pytest

from backend import main
from backend.db import init_db


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
