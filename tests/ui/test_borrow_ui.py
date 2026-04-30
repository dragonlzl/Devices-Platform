from datetime import datetime, timedelta

import httpx
from playwright.sync_api import expect


UNREGISTERED_BORROW_TIP = "未找到该设备的借用人，无法进行设备借用，请找回设备后，把状态改回“正常”。"
TEST_PORTAL_USER = {
    "user_id": "borrow-ui-test-user",
    "open_id": "borrow-ui-test-open",
    "name": "Borrow UI Tester",
    "job_title": "测试",
}


def mock_portal_auth(page):
    user_json = {
        "user_id": TEST_PORTAL_USER["user_id"],
        "open_id": TEST_PORTAL_USER["open_id"],
        "name": TEST_PORTAL_USER["name"],
        "job_title": TEST_PORTAL_USER["job_title"],
    }
    page.route(
        "**/portal-auth.js*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/javascript",
            body=f"""
                window.portalAuth = {{
                  requireJwtUser: async () => ({user_json!r}),
                  requireJwtSession: async () => ({{
                    token: 'borrow-ui-test-token',
                    audience: window.location.origin,
                    user: {user_json!r},
                  }}),
                  getJwtSession: async () => ({{
                    authenticated: true,
                    token: 'borrow-ui-test-token',
                    audience: window.location.origin,
                    user: {user_json!r},
                  }}),
                  clearJwtSession: () => {{}},
                }};
            """,
        ),
    )
    page.route(
        "**/api/current-user/migrate-borrower-data",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"message":"迁移完成","migrated":0}',
        ),
    )


def seed_device(base_url, model="BorrowPhone", status="正常"):
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
                "model": model,
                "status": status,
                "type": "手机",
                "vendor_id": vendor_id,
                "system_id": system_id,
                "system_version_id": version_id,
            },
        )


def update_device_status(base_url, model, status):
    with httpx.Client(base_url=base_url) as client:
        items = client.get("/api/devices").json()["items"]
        device = next(item for item in items if item["model"] == model)
        resp = client.put(
            f"/api/devices/{device['id']}",
            json={
                "model": device["model"],
                "status": status,
                "type": device["type"],
                "vendor_id": device["vendor_id"],
                "system_id": device["system_id"],
                "system_version_id": device["system_version_id"],
                "resolution": device.get("resolution"),
                "arch": device.get("arch"),
                "cpu": device.get("cpu"),
                "boot_password": device.get("boot_password"),
                "notes": device.get("notes"),
            },
        )
        assert resp.status_code == 200


def submit_borrow_request(base_url, model, borrower_name):
    with httpx.Client(base_url=base_url) as client:
        items = client.get("/api/devices").json()["items"]
        device = next(item for item in items if item["model"] == model)
        future_time = datetime.now() + timedelta(days=1)
        resp = client.post(
            f"/api/devices/{device['id']}/borrow",
            json={
                "borrower_name": borrower_name,
                "expected_return_at": future_time.isoformat(),
            },
        )
        assert resp.status_code == 200


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

    row.get_by_role("button", name="点击借用").click()
    page.get_by_label("借用人名字").fill("Tester")
    page.get_by_label("预计归还时间").click()
    expect(page.get_by_text("今天")).to_be_visible()

    future_time = datetime.now() + timedelta(days=1)
    time_str = future_time.strftime("%Y-%m-%dT%H:%M:%S")
    page.get_by_label("预计归还时间").fill(time_str)
    page.get_by_role("button", name="确认借用").click()

    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("已通知管理员")
    expect(page.locator("tr", has_text="BorrowPhone")).to_contain_text("待管理员确认")

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


def test_unregistered_status_blocks_borrow_action(page, base_url):
    seed_device(base_url, model="UnregisteredPhone", status="未登记借用")
    page.goto(f"{base_url}/borrow")
    row = page.locator("tr", has_text="UnregisteredPhone").first
    expect(row).to_be_visible()

    row.get_by_role("button", name="点击借用").click()
    tip = page.locator(".ant-popover-inner-content", has_text=UNREGISTERED_BORROW_TIP)
    expect(tip).to_be_visible()
    page.wait_for_timeout(5200)
    expect(tip).to_be_hidden()

    update_device_status(base_url, "UnregisteredPhone", "正常")
    page.get_by_role("button", name="清除").click()
    row = page.locator("tr", has_text="UnregisteredPhone").first
    expect(row).to_contain_text("正常")
    row.get_by_role("button", name="点击借用").click()
    expect(page.get_by_label("借用人名字")).to_be_visible()


def test_broken_devices_hidden_on_borrow_page_and_normal_search(page, base_url):
    seed_device(base_url, model="VisiblePhone", status="正常")
    seed_device(base_url, model="BrokenPhone", status="损坏")
    page.goto(f"{base_url}/borrow")

    expect(page.locator("tbody tr", has_text="VisiblePhone")).to_have_count(1)
    expect(page.locator("tbody tr", has_text="BrokenPhone")).to_have_count(0)

    page.get_by_placeholder("输入型号/系统/厂商等关键词").fill("BrokenPhone")
    page.get_by_role("button", name="普通搜索").click()
    expect(page.locator("tbody tr", has_text="BrokenPhone")).to_have_count(0)


def test_borrow_page_filters_my_devices_tab(page, base_url):
    mock_portal_auth(page)
    seed_device(base_url, model="MyBorrowedPhone")
    seed_device(base_url, model="OtherBorrowedPhone")
    submit_borrow_request(base_url, "MyBorrowedPhone", TEST_PORTAL_USER["name"])
    submit_borrow_request(base_url, "OtherBorrowedPhone", "Other Borrower")

    page.goto(f"{base_url}/borrow")

    expect(page.get_by_role("menuitem", name="全部设备")).to_be_visible()
    expect(page.locator("tbody tr", has_text="MyBorrowedPhone")).to_have_count(1)
    expect(page.locator("tbody tr", has_text="OtherBorrowedPhone")).to_have_count(1)

    my_menu_item = page.locator(".ant-menu-item", has_text="我借用的")
    expect(my_menu_item).to_be_visible()
    expect(my_menu_item).to_contain_text("1")
    my_menu_item.click()

    expect(page.locator("tbody tr", has_text="MyBorrowedPhone")).to_have_count(1)
    expect(page.locator("tbody tr", has_text="OtherBorrowedPhone")).to_have_count(0)


def test_borrow_sort_resets_page(page, base_url):
    seed_devices(base_url, total=21)
    page.goto(f"{base_url}/borrow")
    page.locator(".ant-pagination-item", has_text="2").first.click()
    expect(page.locator(".ant-pagination-item-active")).to_contain_text("2")
    page.get_by_role("columnheader", name="设备型号").click()
    expect(page.locator(".ant-pagination-item-active")).to_contain_text("1")
