import json

from constants import CATEGORIES


def build_reject_reason_modal(*, approval_id: int, approver_msg_ts: str,
                              channel: str) -> dict:
    """반려 사유를 입력받는 모달. 처리에 필요한 맥락은 private_metadata로 전달."""
    return {
        "type": "modal",
        "callback_id": "reject_reason_submit",
        "private_metadata": json.dumps({
            "approval_id": approval_id,
            "approver_msg_ts": approver_msg_ts,
            "channel": channel,
        }),
        "title": {"type": "plain_text", "text": "반려 사유 입력"},
        "submit": {"type": "plain_text", "text": "반려"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reject_reason",
                "label": {"type": "plain_text", "text": "반려 사유"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "value",
                    "multiline": True,
                    "max_length": 500,
                },
            },
        ],
    }


def build_approval_modal(*, prefill_name: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "approval_submit",
        "title": {"type": "plain_text", "text": "카드 사용 승인 신청"},
        "submit": {"type": "plain_text", "text": "제출"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "requester_name",
                "label": {"type": "plain_text", "text": "신청자 이름"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "value",
                    "initial_value": prefill_name,
                },
            },
            {
                "type": "input",
                "block_id": "category",
                "label": {"type": "plain_text", "text": "사용 용도"},
                "element": {
                    "type": "static_select",
                    "action_id": "value",
                    "options": [
                        {"text": {"type": "plain_text", "text": c}, "value": c}
                        for c in CATEGORIES
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "amount",
                "label": {"type": "plain_text", "text": "금액 (원)"},
                "element": {
                    "type": "number_input",
                    "action_id": "value",
                    "is_decimal_allowed": False,
                    "min_value": "1",
                },
            },
            {
                "type": "input",
                "block_id": "used_date",
                "label": {"type": "plain_text", "text": "사용 날짜"},
                "element": {"type": "datepicker", "action_id": "value"},
            },
            {
                "type": "input",
                "block_id": "merchant",
                "label": {"type": "plain_text", "text": "가맹점명"},
                "element": {"type": "plain_text_input", "action_id": "value"},
            },
        ],
    }
