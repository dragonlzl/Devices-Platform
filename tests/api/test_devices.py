import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


@pytest.fixture()
def client():
    os.environ["APP_DB_FILE"] = "data/apitest.db"
    db_path = Path(__file__).resolve().parents[2] / "data" / "apitest.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    with TestClient(app) as client:
        yield client


def create_vendor_system_version(client):
    vendor = client.post("/api/vendors", json={"name": "Apple"})
    assert vendor.status_code == 200
    system = client.post("/api/systems", json={"name": "iOS"})
    assert system.status_code == 200
    systems = client.get("/api/systems?include_versions=1").json()["items"]
    system_id = systems[0]["id"]
    version = client.post(f"/api/systems/{system_id}/versions", json={"version": "17.0"})
    assert version.status_code == 200
    vendors = client.get("/api/vendors").json()["items"]
    vendor_id = vendors[0]["id"]
    systems = client.get("/api/systems?include_versions=1").json()["items"]
    version_id = systems[0]["versions"][0]["id"]
    return vendor_id, system_id, version_id


def test_device_borrow_return_flow(client):
    vendor_id, system_id, version_id = create_vendor_system_version(client)
    payload = {
        "model": "iPhone 14",
        "status": "正常",
        "type": "手机",
        "vendor_id": vendor_id,
        "system_id": system_id,
        "system_version_id": version_id,
        "resolution": "1170x2532",
        "arch": "arm64",
        "cpu": "A15",
        "boot_password": "1234",
        "notes": "测试机",
    }
    resp = client.post("/api/devices", json=payload)
    assert resp.status_code == 200

    devices = client.get("/api/devices").json()["items"]
    device_id = devices[0]["id"]

    borrow = client.post(
        f"/api/devices/{device_id}/borrow",
        json={
            "borrower_name": "Alice",
            "expected_return_at": "2099-12-31T10:00:00+00:00",
        },
    )
    assert borrow.status_code == 200

    borrowed = client.get("/api/devices").json()["items"][0]
    assert borrowed["loan_status"] == "pending"
    assert borrowed["borrower_name"] == "Alice"
    assert borrowed["borrowed_at"] is None

    requests = client.get("/api/borrow-requests").json()["items"]
    request_id = requests[0]["id"]
    approve = client.post(f"/api/borrow-requests/{request_id}/approve")
    assert approve.status_code == 200

    borrowed = client.get("/api/devices").json()["items"][0]
    assert borrowed["loan_status"] == "borrowed"
    assert borrowed["borrowed_at"] is not None

    extend = client.post(
        f"/api/devices/{device_id}/extend",
        json={"expected_return_at": "2099-12-31T12:00:00+00:00"},
    )
    assert extend.status_code == 200

    returned = client.post(f"/api/devices/{device_id}/return")
    assert returned.status_code == 200

    final = client.get("/api/devices").json()["items"][0]
    assert final["loan_status"] == "available"
    assert final["borrower_name"] is None

    records = client.get("/api/borrow-records").json()["items"]
    assert records[0]["status"] == "returned"
    assert records[0]["returned_at"] is not None


def test_borrow_request_cancel(client):
    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.post(
        "/api/devices",
        json={
            "model": "Pixel 8",
            "status": "正常",
            "type": "手机",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    device_id = client.get("/api/devices").json()["items"][0]["id"]
    borrow = client.post(
        f"/api/devices/{device_id}/borrow",
        json={
            "borrower_name": "Bob",
            "expected_return_at": "2099-12-31T10:00:00+00:00",
        },
    )
    assert borrow.status_code == 200
    pending = client.get("/api/borrow-requests?status=pending")
    assert pending.status_code == 200
    assert len(pending.json()["items"]) == 1
    request_id = client.get("/api/borrow-requests").json()["items"][0]["id"]
    cancel = client.post(f"/api/borrow-requests/{request_id}/cancel")
    assert cancel.status_code == 200
    pending = client.get("/api/borrow-requests?status=pending").json()["items"]
    assert pending == []
    device = client.get("/api/devices").json()["items"][0]
    assert device["loan_status"] == "available"


def test_vendor_rebind_on_delete(client):
    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.post(
        "/api/devices",
        json={
            "model": "iPad",
            "status": "正常",
            "type": "平板",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    client.post("/api/vendors", json={"name": "Samsung"})
    vendors = client.get("/api/vendors").json()["items"]
    target_vendor = next(item for item in vendors if item["name"] == "Samsung")

    resp = client.request("DELETE", f"/api/vendors/{vendor_id}", json={"rebind_vendor_id": None})
    assert resp.status_code == 409

    resp = client.request(
        "DELETE",
        f"/api/vendors/{vendor_id}",
        json={"rebind_vendor_id": target_vendor["id"]},
    )
    assert resp.status_code == 200

    devices = client.get("/api/devices").json()["items"]
    assert devices[0]["vendor_name"] == "Samsung"


def test_version_rebind_on_delete(client):
    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.post(
        "/api/devices",
        json={
            "model": "Pixel",
            "status": "正常",
            "type": "手机",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    client.post(f"/api/systems/{system_id}/versions", json={"version": "18.0"})
    systems = client.get("/api/systems?include_versions=1").json()["items"]
    versions = systems[0]["versions"]
    other_version = next(item for item in versions if item["version"] == "18.0")

    resp = client.request(
        "DELETE", f"/api/versions/{version_id}", json={"rebind_version_id": None}
    )
    assert resp.status_code == 409

    resp = client.request(
        "DELETE",
        f"/api/versions/{version_id}",
        json={"rebind_version_id": other_version["id"]},
    )
    assert resp.status_code == 200

    devices = client.get("/api/devices").json()["items"]
    assert devices[0]["system_version"] == "18.0"


def test_device_query_by_id(client):
    vendor_id, system_id, version_id = create_vendor_system_version(client)
    client.post(
        "/api/devices",
        json={
            "model": "QueryPhone",
            "status": "正常",
            "type": "手机",
            "vendor_id": vendor_id,
            "system_id": system_id,
            "system_version_id": version_id,
        },
    )
    device_id = client.get("/api/devices").json()["items"][0]["id"]
    resp = client.get(f"/api/devices?query={device_id}")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == device_id
