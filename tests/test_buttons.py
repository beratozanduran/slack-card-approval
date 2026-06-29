import pytest
from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.buttons import handle_decision

@pytest.fixture
def setup(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    row = repo.create_pending(
        requester_id="U_REQ", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="김밥천국",
    )
    return conn, repo, row

def test_approve_updates_status_and_msg(setup):
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(),
    )
    updated = repo.get(row["id"])
    assert updated["status"] == "approved"
    client.chat_update.assert_called_once()
    # 로그 채널 + 신청자 DM 둘 다 post되어야 함
    call_channels = [c.kwargs["channel"] for c in client.chat_postMessage.call_args_list]
    assert "C_LOG" in call_channels
    assert "U_REQ" in call_channels

def test_chat_update_failure_does_not_block_others(setup):
    # I1: chat_update가 실패해도 로그/신청자 DM과 sheets_sync는 실행돼야 함
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock()
    client.chat_update.side_effect = Exception("message_not_found")
    sheets = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=sheets,
    )
    assert repo.get(row["id"])["status"] == "approved"
    call_channels = [c.kwargs["channel"] for c in client.chat_postMessage.call_args_list]
    assert "C_LOG" in call_channels
    assert "U_REQ" in call_channels
    sheets.assert_called_once()


def test_requester_dm_includes_context(setup):
    # I5: 결과 DM에 금액·가맹점·용도가 포함돼야 함
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(),
    )
    dm = next(c for c in client.chat_postMessage.call_args_list
             if c.kwargs["channel"] == "U_REQ")
    text = dm.kwargs["text"]
    assert "12,000원" in text
    assert "김밥천국" in text
    assert "점심식비" in text


def test_non_approver_rejected(setup):
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock(); respond = MagicMock()
    body = {
        "user": {"id": "U_HACKER"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(), respond=respond,
    )
    assert repo.get(row["id"])["status"] == "pending"
    respond.assert_called_once()

def test_double_click_ignored(setup):
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock(); respond = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    sheets = MagicMock()
    handle_decision(ack=ack, body=body, client=client, repo=repo, conn=conn,
                    approver_user_id="U_APPR", log_channel_id="C_LOG",
                    sheets_sync=sheets, respond=respond)
    handle_decision(ack=ack, body=body, client=client, repo=repo, conn=conn,
                    approver_user_id="U_APPR", log_channel_id="C_LOG",
                    sheets_sync=sheets, respond=respond)
    assert sheets.call_count == 1  # 두 번째는 무시
