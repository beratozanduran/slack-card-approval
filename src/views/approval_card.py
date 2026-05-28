def _fields(row: dict) -> list:
    return [
        {"type": "mrkdwn", "text": f"*신청자*\n{row['requester_name']}"},
        {"type": "mrkdwn", "text": f"*용도*\n{row['category']}"},
        {"type": "mrkdwn", "text": f"*금액*\n{row['amount']:,}원"},
        {"type": "mrkdwn", "text": f"*사용일*\n{row['used_date']}"},
        {"type": "mrkdwn", "text": f"*가맹점*\n{row['merchant']}"},
        {"type": "mrkdwn", "text": f"*신청일시*\n{row['created_at']}"},
    ]

def build_approval_card(row: dict) -> list:
    aid = str(row["id"])
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"💳 카드 사용 승인 요청 (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
        {"type": "actions", "block_id": "decision", "elements": [
            {"type": "button", "action_id": "approve",
             "text": {"type": "plain_text", "text": "✅ 승인"},
             "style": "primary", "value": aid},
            {"type": "button", "action_id": "reject",
             "text": {"type": "plain_text", "text": "❌ 반려"},
             "style": "danger", "value": aid},
        ]},
    ]

def build_decided_card(row: dict) -> list:
    status_label = "✅ 승인됨" if row["status"] == "approved" else "❌ 반려됨"
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"{status_label} (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
        {"type": "context", "elements": [
            {"type": "mrkdwn",
             "text": f"처리자: <@{row['decided_by']}> · "
                     f"처리일시: {row['decided_at']}"}
        ]},
    ]
