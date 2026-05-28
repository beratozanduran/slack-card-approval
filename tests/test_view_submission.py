from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.view_submission import handle_view_submission

def _view_payload():
    return {
        "callback_id": "approval_submit",
        "state": {"values": {
            "requester_name": {"value": {"value": "Ozan"}},
            "category":       {"value": {"selected_option": {"value": "점심식비"}}},
            "amount":         {"value": {"value": "12000"}},
            "used_date":      {"value": {"selected_date": "2026-05-28"}},
            "merchant":       {"value": {"value": "김밥천국"}},
        }},
    }

def test_inserts_pending_and_dms_approver(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "1.0"}
    ack = MagicMock()
    handle_view_submission(
        ack=ack,
        body={"user": {"id": "U1"}, "view": _view_payload()},
        client=client,
        repo=repo,
        approver_user_id="U_APPR",
    )
    ack.assert_called_once_with()
    rows = conn.execute("SELECT * FROM approvals").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    client.chat_postMessage.assert_called_once()
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "U_APPR"
