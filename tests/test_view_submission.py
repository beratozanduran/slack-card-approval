import json
from unittest.mock import MagicMock
from handlers.view_submission import ack_submission, process_submission


def _view_payload(*, amount="12000", used_date="2026-06-30"):
    return {
        "callback_id": "approval_submit",
        "state": {"values": {
            "requester_name": {"value": {"value": "Ozan"}},
            "category":       {"value": {"selected_option": {"value": "업무교통비"}}},
            "amount":         {"value": {"value": amount}},
            "used_date":      {"value": {"selected_date": used_date}},
            "merchant":       {"value": {"value": "택시"}},
        }},
    }


def _body(**view_kwargs):
    return {"user": {"id": "U1"}, "view": _view_payload(**view_kwargs)}


# --- ack 단계(동기 검증) ---

def test_valid_submission_acks_clean():
    ack = MagicMock()
    ack_submission(ack, _body())
    ack.assert_called_once_with()


def test_future_date_acks_errors():
    ack = MagicMock()
    ack_submission(ack, _body(used_date="2099-01-01"))
    assert ack.call_args.kwargs.get("response_action") == "errors"
    assert "used_date" in ack.call_args.kwargs.get("errors", {})


def test_invalid_amount_acks_errors():
    ack = MagicMock()
    ack_submission(ack, _body(amount="0"))
    assert ack.call_args.kwargs.get("response_action") == "errors"
    assert "amount" in ack.call_args.kwargs.get("errors", {})


# --- 게시 단계(lazy) ---

def test_process_posts_channel_then_dm_with_data_in_button():
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "100.0"}
    process_submission(_body(), client,
                       approver_user_id="U_APPR", log_channel_id="C_LOG")
    channels = [c.kwargs["channel"] for c in client.chat_postMessage.call_args_list]
    assert channels == ["C_LOG", "U_APPR"]
    # 승인자 DM 카드의 버튼 value에 채널 부모 ts를 포함한 신청 데이터가 실려야 함
    dm_blocks = client.chat_postMessage.call_args_list[1].kwargs["blocks"]
    action_block = next(b for b in dm_blocks if b["type"] == "actions")
    data = json.loads(action_block["elements"][0]["value"])
    assert data["channel_msg_ts"] == "100.0"
    assert data["category"] == "업무교통비"
    assert data["amount"] == 12000


def test_process_dm_failure_rolls_back():
    client = MagicMock()
    # 1) 채널 게시 성공, 2) 승인자 DM 실패, 3) 신청자 안내 DM 성공
    client.chat_postMessage.side_effect = [
        {"ts": "100.0"}, Exception("channel_not_found"), None,
    ]
    process_submission(_body(), client,
                       approver_user_id="U_APPR", log_channel_id="C_LOG")
    client.chat_delete.assert_called_once()
    assert client.chat_delete.call_args.kwargs["ts"] == "100.0"
    assert client.chat_postMessage.call_args_list[-1].kwargs["channel"] == "U1"
