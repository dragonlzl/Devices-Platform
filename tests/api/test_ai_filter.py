import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.main import _filter_ai_devices  # noqa: E402


def test_filter_ai_devices_excludes_damaged():
    devices = [
        {"id": 1, "status": "正常"},
        {"id": 2, "status": "损坏"},
        {"id": 3, "status": "报修"},
    ]
    filtered = _filter_ai_devices(devices)
    assert [item["id"] for item in filtered] == [1, 2, 3]
