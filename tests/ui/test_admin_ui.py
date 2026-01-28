from datetime import datetime, timedelta, timezone

import httpx
from playwright.sync_api import expect


def seed_fast_model(base_url):
    with httpx.Client(base_url=base_url) as client:
        client.post(
            "/api/llm/models",
            json={
                "name": "FastModel",
                "api_type": "openai",
                "base_url": "http://example.com",
                "api_key": "test-key",
                "model": "gpt-4o",
                "max_tokens": 128,
                "is_default": True,
            },
        )
        models = client.get("/api/llm/models").json()["items"]
        model_id = models[0]["id"]
        client.post(f"/api/llm/models/{model_id}/assign", json={"role": "fast"})


def seed_borrow_request(base_url):
    with httpx.Client(base_url=base_url) as client:
        vendors = client.get("/api/vendors").json()["items"]
        vendor = next((item for item in vendors if item["name"] == "PendingVendor"), None)
        if not vendor:
            client.post("/api/vendors", json={"name": "PendingVendor"})
            vendors = client.get("/api/vendors").json()["items"]
            vendor = next(item for item in vendors if item["name"] == "PendingVendor")
        vendor_id = vendor["id"]

        systems = client.get("/api/systems?include_versions=1").json()["items"]
        system = next((item for item in systems if item["name"] == "PendingOS"), None)
        if not system:
            client.post("/api/systems", json={"name": "PendingOS"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "PendingOS")
        system_id = system["id"]
        versions = system.get("versions") or []
        if not versions:
            client.post(f"/api/systems/{system_id}/versions", json={"version": "1.0"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "PendingOS")
            versions = system.get("versions") or []
        version_id = versions[0]["id"]
        client.post(
            "/api/devices",
            json={
                "model": "PendingPhone",
                "status": "正常",
                "type": "手机",
                "vendor_id": vendor_id,
                "system_id": system_id,
                "system_version_id": version_id,
            },
        )
        device_id = client.get("/api/devices").json()["items"][0]["id"]
        future_time = datetime.now(timezone.utc) + timedelta(days=1)
        client.post(
            f"/api/devices/{device_id}/borrow",
            json={
                "borrower_name": "PendingUser",
                "expected_return_at": future_time.isoformat(),
            },
        )


def seed_performance_devices(base_url):
    with httpx.Client(base_url=base_url) as client:
        vendors = client.get("/api/vendors").json()["items"]
        vendor = next((item for item in vendors if item["name"] == "PerfVendor"), None)
        if not vendor:
            client.post("/api/vendors", json={"name": "PerfVendor"})
            vendors = client.get("/api/vendors").json()["items"]
            vendor = next(item for item in vendors if item["name"] == "PerfVendor")
        vendor_id = vendor["id"]

        systems = client.get("/api/systems?include_versions=1").json()["items"]
        system = next((item for item in systems if item["name"] == "PerfOS"), None)
        if not system:
            client.post("/api/systems", json={"name": "PerfOS"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "PerfOS")
        system_id = system["id"]
        versions = system.get("versions") or []
        if not versions:
            client.post(f"/api/systems/{system_id}/versions", json={"version": "1.0"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "PerfOS")
            versions = system.get("versions") or []
        version_id = versions[0]["id"]
        devices = [
            ("Perf-High", "性能: 较高"),
            ("Perf-Low", "性能: 较低"),
            ("Perf-Strong", "性能: 强劲"),
            ("Perf-Normal", "性能: 一般"),
        ]
        for model, notes in devices:
            client.post(
                "/api/devices",
                json={
                    "model": model,
                    "status": "正常",
                    "type": "手机",
                    "vendor_id": vendor_id,
                    "system_id": system_id,
                    "system_version_id": version_id,
                    "notes": notes,
                },
            )


def seed_status_devices(base_url):
    with httpx.Client(base_url=base_url) as client:
        vendors = client.get("/api/vendors").json()["items"]
        vendor = next((item for item in vendors if item["name"] == "StatusVendor"), None)
        if not vendor:
            client.post("/api/vendors", json={"name": "StatusVendor"})
            vendors = client.get("/api/vendors").json()["items"]
            vendor = next(item for item in vendors if item["name"] == "StatusVendor")
        vendor_id = vendor["id"]

        systems = client.get("/api/systems?include_versions=1").json()["items"]
        system = next((item for item in systems if item["name"] == "StatusOS"), None)
        if not system:
            client.post("/api/systems", json={"name": "StatusOS"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "StatusOS")
        system_id = system["id"]
        versions = system.get("versions") or []
        if not versions:
            client.post(f"/api/systems/{system_id}/versions", json={"version": "1.0"})
            systems = client.get("/api/systems?include_versions=1").json()["items"]
            system = next(item for item in systems if item["name"] == "StatusOS")
            versions = system.get("versions") or []
        version_id = versions[0]["id"]
        client.post(
            "/api/devices",
            json={
                "model": "Status-Normal",
                "status": "正常",
                "type": "手机",
                "vendor_id": vendor_id,
                "system_id": system_id,
                "system_version_id": version_id,
            },
        )
        client.post(
            "/api/devices",
            json={
                "model": "Status-Broken",
                "status": "损坏",
                "type": "手机",
                "vendor_id": vendor_id,
                "system_id": system_id,
                "system_version_id": version_id,
            },
        )



def test_admin_add_device_validation(page, base_url):
    page.goto(f"{base_url}/admin")
    expect(page.get_by_role("menuitem", name="设备")).to_be_visible()
    expect(page.get_by_role("menuitem", name="待处理")).to_be_visible()
    expect(page.get_by_role("menuitem", name="借用记录")).to_be_visible()
    expect(page.get_by_placeholder("输入型号/系统/厂商等关键词")).to_be_visible()
    expect(page.get_by_text("智能搜索输出")).to_be_visible()
    expect(page.get_by_text("设备总数")).to_be_visible()
    expect(page.get_by_role("button", name="更快")).to_be_visible()
    expect(page.get_by_role("button", name="更准")).to_be_visible()
    expect(page.get_by_role("button", name="打开借用页")).to_be_visible()
    page.get_by_role("button", name="添加设备").click()
    page.get_by_role("button", name="确认").click()
    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("请填写关键字段")

    with page.context.expect_page() as popup_info:
        page.get_by_role("button", name="打开借用页").click()
    popup = popup_info.value
    expect(popup).to_have_url(f"{base_url}/borrow")


def test_admin_ai_mode_persist(page, base_url):
    seed_fast_model(base_url)
    page.add_init_script("() => localStorage.setItem('ai_search_mode','fast')")
    page.goto(f"{base_url}/admin")
    fast_button = page.get_by_role("button", name="更快")
    expect(fast_button.locator(".anticon-check")).to_be_visible()
    page.reload()
    expect(fast_button.locator(".anticon-check")).to_be_visible()


def test_admin_pending_request_flow(page, base_url):
    seed_borrow_request(base_url)
    page.goto(f"{base_url}/admin")
    expect(page.locator(".ant-menu .ant-badge-count")).to_have_text("1")
    page.get_by_role("menuitem", name="待处理").click()
    row = page.locator("tr", has_text="PendingPhone").first
    expect(row).to_be_visible()
    row.get_by_role("button", name="确认").click()
    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("确认借出成功")
    expect(row).to_contain_text("已确认")


def test_admin_performance_sort_order(page, base_url):
    seed_performance_devices(base_url)
    page.goto(f"{base_url}/admin")
    page.get_by_placeholder("输入型号/系统/厂商等关键词").fill("Perf-")
    page.get_by_role("button", name="搜索").click()
    rows = page.locator("tbody tr").filter(has_text="Perf-")
    expect(rows).to_have_count(4)

    page.get_by_role("columnheader", name="性能").click()
    expect(rows.nth(0)).to_contain_text("Perf-Strong")
    expect(rows.nth(1)).to_contain_text("Perf-High")
    expect(rows.nth(2)).to_contain_text("Perf-Normal")
    expect(rows.nth(3)).to_contain_text("Perf-Low")

    page.get_by_role("columnheader", name="性能").click()
    expect(rows.nth(0)).to_contain_text("Perf-Low")
    expect(rows.nth(1)).to_contain_text("Perf-Normal")
    expect(rows.nth(2)).to_contain_text("Perf-High")
    expect(rows.nth(3)).to_contain_text("Perf-Strong")


def test_admin_status_sort_normal_first(page, base_url):
    seed_status_devices(base_url)
    page.goto(f"{base_url}/admin")
    page.get_by_placeholder("输入型号/系统/厂商等关键词").fill("Status-")
    page.get_by_role("button", name="搜索").click()
    rows = page.locator("tbody tr").filter(has_text="Status-")
    expect(rows).to_have_count(2)

    page.get_by_role("columnheader", name="设备状态").click()
    expect(rows.nth(0)).to_contain_text("Status-Normal")


def test_admin_device_form_quick_add_buttons(page, base_url):
    page.goto(f"{base_url}/admin")
    page.get_by_role("button", name="添加设备").click()
    expect(page.locator(".ant-drawer-title", has_text="添加设备")).to_be_visible()

    vendor_select = page.locator(".ant-form-item", has_text="厂商").locator(".ant-select")
    vendor_select.click()
    expect(page.get_by_role("button", name="新增厂商")).to_be_visible()
    page.get_by_role("button", name="新增厂商").click()
    expect(page.locator(".ant-drawer-title", has_text="新增厂商")).to_be_visible()
    page.locator(".ant-drawer-open").get_by_role("button", name="取消").click()
    expect(page.locator(".ant-drawer-title", has_text="添加设备")).to_be_visible()

    system_select = page.locator(".ant-form-item", has_text="系统").locator(".ant-select")
    system_select.click()
    expect(page.get_by_role("button", name="新增系统")).to_be_visible()
    page.keyboard.press("Escape")

    version_select = page.locator(".ant-form-item", has_text="系统版本").locator(".ant-select")
    version_select.click()
    expect(page.get_by_role("button", name="新增版本")).to_be_visible()
    page.get_by_role("button", name="新增版本").click()
    notice = page.locator(".ant-message-notice").first
    expect(notice).to_contain_text("请先选择系统")
