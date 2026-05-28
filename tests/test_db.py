from db import connect, init_schema


def test_init_schema_creates_tables(tmp_path):
    db_path = tmp_path / "t.db"
    conn = connect(str(db_path))
    init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "approvals" in tables
    assert "sheets_sync_queue" in tables
