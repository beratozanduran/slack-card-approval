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


def _call(conn, repo, client, ack, body):
    handle_view_submission(
        ack=ack, body=body, client=client, repo=repo,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
    )


def test_posts_channel_card_then_dms_approver(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "100.0"}
    ack = MagicMock()
    _call(conn, repo, client, ack,
          {"user": {"id": "U1"}, "view": _view_payload()})

    ack.assert_called_once_with()
    rows = conn.execute("SELECT * FROM approvals").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    # 부모 메시지 ts가 저장돼야 함(스레드 기준점)
    assert rows[0]["channel_msg_ts"] == "100.0"
    # 1) 로그 채널 대기중 카드, 2) 승인자 DM
    channels = [c.kwargs["channel"] for c in client.chat_postMessage.call_args_list]
    assert channels == ["C_LOG", "U_APPR"]


def test_future_date_rejected_with_errors(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    ack = MagicMock()
    _call(conn, repo, client, ack,
          {"user": {"id": "U1"}, "view": _view_payload(used_date="2099-01-01")})
    ack.assert_called_once()
    assert ack.call_args.kwargs.get("response_action") == "errors"
    assert "used_date" in ack.call_args.kwargs.get("errors", {})
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    client.chat_postMessage.assert_not_called()


def test_invalid_amount_rejected_with_errors(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    ack = MagicMock()
    _call(conn, repo, client, ack,
          {"user": {"id": "U1"}, "view": _view_payload(amount="0")})
    assert ack.call_args.kwargs.get("response_action") == "errors"
    assert "amount" in ack.call_args.kwargs.get("errors", {})
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0


def test_channel_post_failure_deletes_pending_row(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    # 채널 게시 실패 → row 삭제 + 신청자 안내 DM
    client.chat_postMessage.side_effect = [Exception("channel_not_found"), None]
    ack = MagicMock()
    _call(conn, repo, client, ack,
          {"user": {"id": "U1"}, "view": _view_payload()})
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    # 마지막 호출은 신청자(U1) 오류 안내
    assert client.chat_postMessage.call_args_list[-1].kwargs["channel"] == "U1"


def test_approver_dm_failure_rolls_back(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    # 1) 채널 게시 성공, 2) 승인자 DM 실패, 3) 신청자 안내 DM 성공
    client.chat_postMessage.side_effect = [
        {"ts": "100.0"}, Exception("channel_not_found"), None,
    ]
    ack = MagicMock()
    _call(conn, repo, client, ack,
          {"user": {"id": "U1"}, "view": _view_payload()})
    # 좀비 row가 남지 않고, 채널 대기중 카드도 삭제돼야 함
    assert conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0
    client.chat_delete.assert_called_once()
    assert client.chat_delete.call_args.kwargs["ts"] == "100.0"
    assert client.chat_postMessage.call_args_list[-1].kwargs["channel"] == "U1"
