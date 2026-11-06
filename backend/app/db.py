"""SQLite database access.

A single connection guarded by a re-entrant lock keeps writes serialized and
is plenty for a local single-user application. WAL mode allows readers to
proceed while a write is in progress.
"""
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import settings
from .migrations import MIGRATIONS

_lock = threading.RLock()
_conn: Optional[sqlite3.Connection] = None


def _row_to_dict(row: sqlite3.Row, *args: Any, **kwargs: Any) -> dict:
    raise NotImplementedError


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create a new raw connection (used by tests with temporary databases)."""
    path = Path(db_path) if db_path is not None else settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def get_conn() -> sqlite3.Connection:
    """Return the process-wide connection, initializing the schema if needed."""
    global _conn
    with _lock:
        if _conn is None:
            _conn = connect()
            migrate(_conn)
        return _conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """Transaction context: BEGIN ... COMMIT/ROLLBACK with the global lock."""
    conn = get_conn()
    with _lock:
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SELECT and return all rows as dicts (JSON columns already parsed)."""
    conn = get_conn()
    with _lock:
        cur = conn.execute(sql, params)
        rows = cur.fetchall()
    return [decode_row(dict(r)) for r in rows]


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    """Run a single write statement inside a transaction. Returns lastrowid."""
    with tx() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid or 0


def executescript(conn: sqlite3.Connection, script: str) -> None:
    conn.executescript(script)


def decode_row(row: dict) -> dict:
    """Parse JSON columns named in migrations into Python objects."""
    json_cols = {
        "objectives", "sections", "example", "quiz", "answer", "hints",
        "solution", "test_spec", "submission", "feedback", "details",
        "prerequisites", "meta", "skills", "requirements", "milestones",
        "challenges", "outline", "params", "options",
    }
    for key in list(row.keys()):
        if key in json_cols and isinstance(row[key], str):
            try:
                row[key] = json.loads(row[key])
            except (ValueError, TypeError):
                pass  # leave as-is; never crash a read over bad legacy data
    return row


def migrate(conn: sqlite3.Connection) -> None:
    """Apply pending migrations in order. Safe to call repeatedly."""
    with _lock:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY,"
            " applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
        for version, script in MIGRATIONS:
            if version in applied:
                continue
            conn.executescript(script)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        conn.commit()


def close() -> None:
    """Close the shared connection (used by tests and graceful shutdown)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def set_conn_for_tests(conn: sqlite3.Connection) -> None:
    """Point the module at a dedicated connection (used by the test suite)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = conn
        migrate(conn)
