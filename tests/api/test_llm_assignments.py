import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.db import db_session, init_db  # noqa: E402
from backend.main import _assign_llm_model, _clear_llm_assignment, _get_int_setting  # noqa: E402


@pytest.fixture()
def conn():
    os.environ["APP_DB_FILE"] = "data/apitest.db"
    db_path = Path(__file__).resolve().parents[2] / "data" / "apitest.db"
    if db_path.exists():
        db_path.unlink()
    init_db()
    with db_session() as session:
        yield session


def create_model(conn, name: str):
    cur = conn.execute(
        """
        INSERT INTO llm_models (name, api_type, base_url, api_key, model, max_tokens, is_default, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, "now", "now")
        """,
        (name, "openai", "http://example.com", "test-key", "gpt-4o", 16),
    )
    return cur.lastrowid


def test_assignments_unique(conn):
    model_fast = create_model(conn, "fast")
    model_acc = create_model(conn, "accurate")

    assert _get_int_setting(conn, "llm_fast_model_id") is None
    assert _get_int_setting(conn, "llm_accurate_model_id") is None

    _assign_llm_model(conn, model_fast, "fast")
    assert _get_int_setting(conn, "llm_fast_model_id") == model_fast

    with pytest.raises(Exception):
        _assign_llm_model(conn, model_fast, "accurate")

    _assign_llm_model(conn, model_acc, "accurate")
    assert _get_int_setting(conn, "llm_accurate_model_id") == model_acc

    _clear_llm_assignment(conn, "fast")
    assert _get_int_setting(conn, "llm_fast_model_id") is None
