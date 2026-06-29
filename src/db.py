import sqlite3
from pathlib import Path

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


# 기존 DB에 누락된 컬럼을 idempotent하게 추가하는 마이그레이션 정의.
# (CREATE TABLE IF NOT EXISTS는 기존 테이블에 새 컬럼을 더하지 않으므로 별도 처리)
_MIGRATIONS = {
    "approvals": {
        "decided_by_name": "TEXT",
        "reject_reason": "TEXT",
        "channel_msg_ts": "TEXT",
    },
}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, columns in _MIGRATIONS.items():
        existing = {
            r["name"]
            for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, decl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)
