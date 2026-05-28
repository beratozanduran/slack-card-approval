import pytest
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo, ApprovalNotPending

@pytest.fixture
def repo(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_schema(conn)
    return ApprovalRepo(conn)

def test_create_pending_returns_row(repo):
    row = repo.create_pending(
        requester_id="U1", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="김밥천국",
    )
    assert row["id"] >= 1
    assert row["status"] == "pending"

def test_decide_sets_status_and_decider(repo):
    row = repo.create_pending(
        requester_id="U1", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="x",
    )
    decided = repo.decide(row["id"], "approved", "U2", "1234.5678")
    assert decided["status"] == "approved"
    assert decided["decided_by"] == "U2"
    assert decided["approver_msg_ts"] == "1234.5678"

def test_decide_twice_raises(repo):
    row = repo.create_pending(
        requester_id="U1", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="x",
    )
    repo.decide(row["id"], "approved", "U2", "1.0")
    with pytest.raises(ApprovalNotPending):
        repo.decide(row["id"], "rejected", "U2", "1.0")
