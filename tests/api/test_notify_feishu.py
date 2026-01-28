from notify_feishu import extract_latest_update


def test_extract_latest_update_from_line():
    line = (
        "- 更新记录：2026-01-27 完成 A。2026-01-28 修复 B。2026-01-29 新增 C。"
    )
    assert extract_latest_update(line) == "2026-01-29 新增 C"


def test_extract_latest_update_single_entry():
    line = "- 更新记录：2026-01-27 仅一条更新"
    assert extract_latest_update(line) == "2026-01-27 仅一条更新"


def test_extract_latest_update_missing_label():
    assert extract_latest_update("无关内容") == ""
