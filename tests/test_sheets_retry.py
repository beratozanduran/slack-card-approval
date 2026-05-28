from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from services.sheets_retry import enqueue, drain_once


def test_enqueue_then_drain(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    row = repo.create_pending(
        requester_id="U", requester_name="x", category="기타비용",
        amount=1, used_date=date(2026, 5, 28), merchant="m",
    )
    repo.decide(row["id"], "approved", "U2", "1.0")
    enqueue(conn, row["id"], "boom")
    pending = conn.execute(
        "SELECT * FROM sheets_sync_queue").fetchall()
    assert len(pending) == 1

    # next_retry_at은 5분 뒤로 설정되므로, 테스트에서는 과거로 강제 이동
    conn.execute(
        "UPDATE sheets_sync_queue SET next_retry_at = datetime('now', '-1 minute')"
    )
    conn.commit()

    sync = MagicMock()
    drain_once(conn, repo, sync)
    sync.assert_called_once()
    after = conn.execute("SELECT * FROM sheets_sync_queue").fetchall()
    assert after == []
