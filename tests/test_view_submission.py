from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.view_submission import handle_view_submission

def _view_payload(*, amount="12000", used_date="2026-05-28"):
    return {
        "callback_id": "approval_submit",
        "state": {"values": {
            "requester_name": {"value": {"value": "Ozan"}},
            "category":       {"value": {"selected_option": {"value": "점심식비"}}},
            "amount":         {"value": {"value": amount}},
            "used_date":      {"value": {"selected_date": used_date}},
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


def test_future_date_rejected_with_errors(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    ack = MagicMock()
    handle_view_submission(
        ack=ack,
        body={"user": {"id": "U1"},
              "view": _view_payload(used_date="2099-01-01")},
        client=client,
        repo=repo,
        approver_user_id="U_APPR",
    )
    # 모달을 닫지 않고 used_date 에러를 표시해야 함
    ack.assert_called_once()
    assert ack.call_args.kwargs.get("response_action") == "errors"
    assert "used_date" in ack.call_args.kwargs.get("errors", {})
    # row가 생성되지 않아야 함
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    client.chat_postMessage.assert_not_called()


def test_invalid_amount_rejected_with_errors(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    ack = MagicMock()
    handle_view_submission(
        ack=ack,
        body={"user": {"id": "U1"}, "view": _view_payload(amount="0")},
        client=client,
        repo=repo,
        approver_user_id="U_APPR",
    )
    assert ack.call_args.kwargs.get("response_action") == "errors"
    assert "amount" in ack.call_args.kwargs.get("errors", {})
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0


def test_approver_dm_failure_deletes_pending_row(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    # 승인자 DM은 실패, 신청자 안내 DM은 성공하도록 설정
    client.chat_postMessage.side_effect = [Exception("channel_not_found"), None]
    ack = MagicMock()
    handle_view_submission(
        ack=ack,
        body={"user": {"id": "U1"}, "view": _view_payload()},
        client=client,
        repo=repo,
        approver_user_id="U_APPR",
    )
    ack.assert_called_once_with()
    # 좀비 pending row가 남지 않아야 함
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    # 신청자에게 재시도 안내 DM이 전송돼야 함
    assert client.chat_postMessage.call_count == 2
    last = client.chat_postMessage.call_args_list[-1].kwargs
    assert last["channel"] == "U1"
