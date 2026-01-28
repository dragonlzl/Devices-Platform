from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.main import _format_notify_time  # noqa: E402


def test_format_notify_time_from_str():
    assert _format_notify_time("2024-01-01T00:00:00+00:00") == "2024-01-01 08:00:00"


def test_format_notify_time_from_datetime():
    value = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert _format_notify_time(value) == "2024-01-01 08:00:00"
