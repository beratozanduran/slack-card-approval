import json
import pytest
from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.buttons import handle_decision, handle_reject_reason


@pytest.fixture
def setup(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    row = repo.create_pending(
        requester_id="U_REQ", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="김밥천국",
    )
    # 신청 시 채널에 게시된 부모 메시지 ts를 저장(스레드 기준점)
    repo.set_channel_msg_ts(row["id"], "100.0")
    row = repo.get(row["id"])
    return conn, repo, row


def _client():
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "승인자"}}
    }
    return client


def _approve_body(row):
    return {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }


def _thread_calls(client):
    return [c for c in client.chat_postMessage.call_args_list
            if c.kwargs.get("thread_ts") == "100.0"]


def test_approve_updates_status_and_threads_result(setup):
    conn, repo, row = setup
    client = _client(); ack = MagicMock()
    handle_decision(
        ack=ack, body=_approve_body(row), client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(),
    )
    updated = repo.get(row["id"])
    assert updated["status"] == "approved"
    assert updated["decided_by_name"] == "승인자"
    # 승인자 DM 카드 + 채널 부모 카드 모두 갱신
    assert client.chat_update.call_count == 2
    # 결과는 부모 메시지의 스레드 답글로(공개), 신청자 DM은 없어야 함
    threads = _thread_calls(client)
    assert len(threads) == 1
    assert threads[0].kwargs["channel"] == "C_LOG"
    dm_to_requester = [c for c in client.chat_postMessage.call_args_list
                       if c.kwargs.get("channel") == "U_REQ"]
    assert dm_to_requester == []


def test_chat_update_failure_does_not_block_thread_and_sheets(setup):
    conn, repo, row = setup
    client = _client(); ack = MagicMock()
    client.chat_update.side_effect = Exception("message_not_found")
    sheets = MagicMock()
    handle_decision(
        ack=ack, body=_approve_body(row), client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG", sheets_sync=sheets,
    )
    assert repo.get(row["id"])["status"] == "approved"
    assert len(_thread_calls(client)) == 1
    sheets.assert_called_once()


def test_thread_result_mentions_requester(setup):
    conn, repo, row = setup
    client = _client(); ack = MagicMock()
    handle_decision(
        ack=ack, body=_approve_body(row), client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(),
    )
    text = _thread_calls(client)[0].kwargs["text"]
    assert "<@U_REQ>" in text
    assert "승인" in text


def test_non_approver_rejected(setup):
    conn, repo, row = setup
    client = _client(); ack = MagicMock(); respond = MagicMock()
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
    client = _client(); ack = MagicMock(); respond = MagicMock()
    sheets = MagicMock()
    for _ in range(2):
        handle_decision(ack=ack, body=_approve_body(row), client=client,
                        repo=repo, conn=conn, approver_user_id="U_APPR",
                        log_channel_id="C_LOG", sheets_sync=sheets,
                        respond=respond)
    assert sheets.call_count == 1  # 두 번째는 무시


def test_reject_button_opens_reason_modal(setup):
    conn, repo, row = setup
    client = _client(); ack = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "reject", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
        "trigger_id": "TR1",
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo, conn=conn,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(),
    )
    # 아직 처리되지 않고 사유 모달만 열려야 함
    assert repo.get(row["id"])["status"] == "pending"
    client.views_open.assert_called_once()
    view = client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "reject_reason_submit"
    meta = json.loads(view["private_metadata"])
    assert meta["approval_id"] == row["id"]


def test_reject_reason_submit_saves_reason_and_threads(setup):
    conn, repo, row = setup
    client = _client(); ack = MagicMock()
    sheets = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "view": {
            "private_metadata": json.dumps({
                "approval_id": row["id"], "approver_msg_ts": "1.0",
                "channel": "D1",
            }),
            "state": {"values": {
                "reject_reason": {"value": {"value": "영수증 누락"}}
            }},
        },
    }
    handle_reject_reason(
        ack=ack, body=body, client=client, repo=repo, conn=conn,
        log_channel_id="C_LOG", sheets_sync=sheets,
    )
    updated = repo.get(row["id"])
    assert updated["status"] == "rejected"
    assert updated["reject_reason"] == "영수증 누락"
    text = _thread_calls(client)[0].kwargs["text"]
    assert "영수증 누락" in text
    assert "반려" in text
    sheets.assert_called_once()
