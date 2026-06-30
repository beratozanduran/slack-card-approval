import json
from unittest.mock import MagicMock
import pytest
from handlers.buttons import (
    handle_approve, handle_reject_open, handle_reject_reason,
)

ROW = {
    "id": "260630-101010", "requester_id": "U_REQ", "requester_name": "Ozan",
    "category": "업무교통비", "amount": 12000, "used_date": "2026-06-30",
    "merchant": "택시", "created_at": "2026-06-30 10:10:10",
    "channel_msg_ts": "100.0",
}


def _client():
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "승인자"}}
    }
    return client


def _approve_body(user="U_APPR"):
    return {
        "user": {"id": user},
        "actions": [{"action_id": "approve", "value": json.dumps(ROW)}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }


def _thread_calls(client):
    return [c for c in client.chat_postMessage.call_args_list
            if c.kwargs.get("thread_ts") == "100.0"]


def test_approve_finalizes_and_threads(monkeypatch):
    client = _client()
    sheets = MagicMock()
    handle_approve(_approve_body(), client, approver_user_id="U_APPR",
                   log_channel_id="C_LOG", sheets_sync=sheets)
    # 승인자 DM 카드 + 채널 부모 카드 갱신
    assert client.chat_update.call_count == 2
    # 결과는 공개 스레드 답글, 신청자 DM 없음
    assert len(_thread_calls(client)) == 1
    assert not [c for c in client.chat_postMessage.call_args_list
                if c.kwargs.get("channel") == "U_REQ"]
    # Sheets에 승인 상태 + 승인자 이름으로 기록
    sheets.assert_called_once()
    row = sheets.call_args.args[0]
    assert row["status"] == "approved"
    assert row["decided_by_name"] == "승인자"


def test_approve_rejected_for_non_approver():
    client = _client()
    sheets = MagicMock()
    handle_approve(_approve_body(user="U_HACK"), client,
                   approver_user_id="U_APPR", log_channel_id="C_LOG",
                   sheets_sync=sheets)
    client.chat_postEphemeral.assert_called_once()
    sheets.assert_not_called()
    client.chat_update.assert_not_called()


def test_thread_text_clean_format():
    client = _client()
    handle_approve(_approve_body(), client, approver_user_id="U_APPR",
                   log_channel_id="C_LOG", sheets_sync=MagicMock())
    text = _thread_calls(client)[0].kwargs["text"]
    assert "<@U_REQ>" in text
    assert "업무교통비" in text
    assert "승인" in text
    assert "#" not in text and "*" not in text


def test_reject_open_opens_reason_modal():
    client = _client(); ack = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "reject", "value": json.dumps(ROW)}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"}, "trigger_id": "TR1",
    }
    handle_reject_open(ack, body, client, approver_user_id="U_APPR")
    ack.assert_called_once()
    client.views_open.assert_called_once()
    view = client.views_open.call_args.kwargs["view"]
    assert view["callback_id"] == "reject_reason_submit"
    meta = json.loads(view["private_metadata"])
    assert meta["row"]["id"] == ROW["id"]
    assert meta["approver_msg_ts"] == "1.0"


def test_reject_reason_finalizes_with_reason():
    client = _client(); sheets = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "view": {
            "private_metadata": json.dumps(
                {"row": ROW, "approver_msg_ts": "1.0", "channel": "D1"}
            ),
            "state": {"values": {
                "reject_reason": {"value": {"value": "영수증 누락"}}
            }},
        },
    }
    handle_reject_reason(body, client, log_channel_id="C_LOG", sheets_sync=sheets)
    row = sheets.call_args.args[0]
    assert row["status"] == "rejected"
    assert row["reject_reason"] == "영수증 누락"
    text = _thread_calls(client)[0].kwargs["text"]
    assert "영수증 누락" in text and "반려" in text


def test_sheets_failure_posts_warning(monkeypatch):
    monkeypatch.setattr("handlers.buttons.time.sleep", lambda *_: None)
    client = _client()
    sheets = MagicMock(side_effect=Exception("quota exceeded"))
    handle_approve(_approve_body(), client, approver_user_id="U_APPR",
                   log_channel_id="C_LOG", sheets_sync=sheets)
    assert sheets.call_count == 3  # 인라인 재시도
    warn = [c for c in _thread_calls(client) if "실패" in c.kwargs.get("text", "")]
    assert len(warn) == 1
