from datetime import datetime, timedelta

import httpx
from playwright.sync_api import expect


def seed_device(base_url):
    with httpx.Client(base_url=base_url) as client:
        vendors = client.get("/api/vendors").json()["items"]
        vendor = next((item for item in vendors if item["name"] == "BorrowVendor"), None)
        if not vendor:
            client.post("/api/vendors", json={"name": "BorrowVendor"})
            vendors = client.get("/api/vendors").json()["items"]
            vendor = next(item for item in vendors if item["name"] == "BorrowVendor")
        vendor_id = vendor["id"]

        systems = client.get("/api/systems?include_versions=1").json()["items"]
        system = next((item for item in systems if item["name"] == "BorrowOS"), None)
        if not system:
            client.post("/api/systems", json={"name": "BorrowOS"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "BorrowOS")
        system_id = system["id"]
        versions = system.get("versions") or []
        if not versions:
            client.post(f"/api/systems/{system_id}/versions", json={"version": "1.0"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "BorrowOS")
            versions = system.get("versions") or []
        version_id = versions[0]["id"]
        client.post(
            "/api/devices",
            json={
                "model": "BorrowPhone",
                "status": "正常",
                "type": "手机",
                "vendor_id": vendor_id,
                "system_id": system_id,
                "system_version_id": version_id,
            },
        )


def seed_devices(base_url, total):
    with httpx.Client(base_url=base_url) as client:
        vendors = client.get("/api/vendors").json()["items"]
        vendor = next((item for item in vendors if item["name"] == "BorrowVendor"), None)
        if not vendor:
            client.post("/api/vendors", json={"name": "BorrowVendor"})
            vendors = client.get("/api/vendors").json()["items"]
            vendor = next(item for item in vendors if item["name"] == "BorrowVendor")
        vendor_id = vendor["id"]

        systems = client.get("/api/systems?include_versions=1").json()["items"]
        system = next((item for item in systems if item["name"] == "BorrowOS"), None)
        if not system:
            client.post("/api/systems", json={"name": "BorrowOS"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "BorrowOS")
        system_id = system["id"]
        versions = system.get("versions") or []
        if not versions:
            client.post(f"/api/systems/{system_id}/versions", json={"version": "1.0"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "BorrowOS")
            versions = system.get("versions") or []
        version_id = versions[0]["id"]
        for idx in range(total):
            client.post(
                "/api/devices",
                json={
                    "model": f"BorrowPhone-{idx}",
                    "status": "正常",
                    "type": "手机",
                    "vendor_id": vendor_id,
                    "system_id": system_id,
                    "system_version_id": version_id,
                },
            )


def test_borrow_flow(page, base_url):
    seed_device(base_url)
    page.goto(f"{base_url}/borrow")
    expect(page.get_by_placeholder("输入型号/系统/厂商等关键词")).to_be_visible()
    expect(page.get_by_text("智能搜索输出")).to_be_visible()
    expect(page.get_by_text("设备总数")).to_be_visible()
    expect(page.get_by_role("button", name="更快")).to_be_visible()
    expect(page.get_by_role("button", name="更准")).to_be_visible()
    row = page.locator("tr", has_text="BorrowPhone").first
    expect(row).to_be_visible()

    row.get_by_role("button", name="可借用").click()
    page.get_by_label("借用人名字").fill("Tester")
    page.get_by_label("预计归还时间").click()
    expect(page.get_by_text("今天")).to_be_visible()

    future_time = datetime.now() + timedelta(days=1)
    time_str = future_time.strftime("%Y-%m-%dT%H:%M:%S")
    page.get_by_label("预计归还时间").fill(time_str)
    page.get_by_role("button", name="确认借用").click()

    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("已通知管理员")
    expect(page.locator("tr", has_text="BorrowPhone")).to_contain_text("待借出")

    row.get_by_role("button", name="换借用人").click()
    page.get_by_label("借用人名字").fill("Tester-2")
    new_time = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
    page.get_by_label("预计归还时间").fill(new_time)
    page.get_by_role("button", name="确认").click()
    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("已发送通知到管理员")
    expect(page.locator("tr", has_text="BorrowPhone")).to_contain_text("Tester")

    row.get_by_role("button", name="换借用人").click()
    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("当前设备已有借用人更换申请，需等待管理员处理")


def test_borrow_sort_resets_page(page, base_url):
    seed_devices(base_url, total=21)
    page.goto(f"{base_url}/borrow")
    page.locator(".ant-pagination-item", has_text="2").first.click()
    expect(page.locator(".ant-pagination-item-active")).to_contain_text("2")
    page.get_by_role("columnheader", name="设备型号").click()
    expect(page.locator(".ant-pagination-item-active")).to_contain_text("1")
