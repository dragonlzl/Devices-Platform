import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


DEFAULT_DB_FILE = "data/app.db"


def get_db_path() -> str:
    db_file = os.environ.get("APP_DB_FILE", "").strip()
    if not db_file:
        db_file = DEFAULT_DB_FILE
    if not os.path.isabs(db_file):
        db_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_file)
    os.makedirs(os.path.dirname(db_file), exist_ok=True)
    return db_file


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db() -> sqlite3.Connection:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _ensure_person_snapshot_columns(conn: sqlite3.Connection) -> None:
    borrower_columns = {
        "borrower_user_id": "TEXT",
        "borrower_open_id": "TEXT",
        "borrower_avatar_url": "TEXT",
        "borrower_job_title": "TEXT",
    }
    for table in ("devices", "borrow_requests", "borrow_records"):
        _ensure_columns(conn, table, borrower_columns)

    _ensure_columns(
        conn,
        "borrow_changes",
        {
            "borrower_before_user_id": "TEXT",
            "borrower_before_open_id": "TEXT",
            "borrower_before_avatar_url": "TEXT",
            "borrower_before_job_title": "TEXT",
            "borrower_after_user_id": "TEXT",
            "borrower_after_open_id": "TEXT",
            "borrower_after_avatar_url": "TEXT",
            "borrower_after_job_title": "TEXT",
        },
    )


@contextmanager
def db_session():
    conn = connect_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS systems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS system_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                version TEXT NOT NULL,
                UNIQUE(system_id, version),
                FOREIGN KEY (system_id) REFERENCES systems(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                status TEXT NOT NULL,
                type TEXT,
                vendor_id INTEGER NOT NULL,
                system_id INTEGER NOT NULL,
                system_version_id INTEGER NOT NULL,
                resolution TEXT,
                arch TEXT,
                cpu TEXT,
                boot_password TEXT,
                notes TEXT,
                loan_status TEXT NOT NULL DEFAULT 'available',
                borrower_name TEXT,
                borrower_user_id TEXT,
                borrower_open_id TEXT,
                borrower_avatar_url TEXT,
                borrower_job_title TEXT,
                borrowed_at TEXT,
                expected_return_at TEXT,
                overdue_notified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (vendor_id) REFERENCES vendors(id),
                FOREIGN KEY (system_id) REFERENCES systems(id),
                FOREIGN KEY (system_version_id) REFERENCES system_versions(id)
            );

            CREATE TABLE IF NOT EXISTS borrow_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                device_model TEXT NOT NULL,
                borrower_name TEXT NOT NULL,
                borrower_user_id TEXT,
                borrower_open_id TEXT,
                borrower_avatar_url TEXT,
                borrower_job_title TEXT,
                expected_return_at TEXT NOT NULL,
                request_type TEXT NOT NULL,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                handled_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices(id)
            );

            CREATE TABLE IF NOT EXISTS borrow_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                device_model TEXT NOT NULL,
                borrower_name TEXT NOT NULL,
                borrower_user_id TEXT,
                borrower_open_id TEXT,
                borrower_avatar_url TEXT,
                borrower_job_title TEXT,
                borrowed_at TEXT NOT NULL,
                expected_return_at TEXT,
                returned_at TEXT,
                status TEXT NOT NULL,
                request_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (request_id) REFERENCES borrow_requests(id)
            );

            CREATE TABLE IF NOT EXISTS borrow_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER NOT NULL,
                record_id INTEGER,
                request_id INTEGER,
                borrower_before TEXT,
                borrower_before_user_id TEXT,
                borrower_before_open_id TEXT,
                borrower_before_avatar_url TEXT,
                borrower_before_job_title TEXT,
                borrower_after TEXT,
                borrower_after_user_id TEXT,
                borrower_after_open_id TEXT,
                borrower_after_avatar_url TEXT,
                borrower_after_job_title TEXT,
                expected_before TEXT,
                expected_after TEXT,
                changed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (device_id) REFERENCES devices(id),
                FOREIGN KEY (record_id) REFERENCES borrow_records(id),
                FOREIGN KEY (request_id) REFERENCES borrow_requests(id)
            );

            CREATE TABLE IF NOT EXISTS llm_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_type TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                model TEXT NOT NULL,
                max_tokens INTEGER NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        _ensure_person_snapshot_columns(conn)
