import json


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
    """승인자 DM용 카드 — 승인/반려 버튼 포함.

    DB가 없으므로 신청 데이터 전체를 버튼 value(JSON)에 실어 결정 시점까지 운반한다.
    (Slack 버튼 value 최대 2000자 — 본 페이로드는 충분히 작다.)
    """
    payload = json.dumps(row, ensure_ascii=False)
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"💳 에듀카드 사용 요청 (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
        {"type": "actions", "block_id": "decision", "elements": [
            {"type": "button", "action_id": "approve",
             "text": {"type": "plain_text", "text": "✅ 승인"},
             "style": "primary", "value": payload},
            {"type": "button", "action_id": "reject",
             "text": {"type": "plain_text", "text": "❌ 반려"},
             "style": "danger", "value": payload},
        ]},
    ]


def build_pending_channel_card(row: dict) -> list:
    """로그 채널 게시용 '대기중' 카드 — 버튼 없음. 결과는 이 메시지의 스레드에 남는다."""
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"💳 에듀카드 사용 요청 (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
        {"type": "context", "elements": [
            {"type": "mrkdwn",
             "text": f"⏳ *승인 대기중* · 신청자: <@{row['requester_id']}>"}
        ]},
    ]


def build_decided_card(row: dict) -> list:
    """결정 후 카드 — 승인자 DM 카드와 채널 부모 카드 갱신에 함께 사용."""
    status_label = "✅ 승인됨" if row["status"] == "approved" else "❌ 반려됨"
    blocks = [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"{status_label} (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
    ]
    if row["status"] == "rejected" and row.get("reject_reason"):
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": f"*반려 사유*\n{row['reject_reason']}"},
        })
    decider = row.get("decided_by_name") or f"<@{row['decided_by']}>"
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn",
         "text": f"처리자: {decider} · 처리일시: {row['decided_at']}"}
    ]})
    return blocks


def build_thread_result_text(row: dict) -> str:
    """채널 스레드에 남길 결과 답글 — 신청자를 멘션해 알림이 가게 한다(DM 대체)."""
    verb = "승인" if row["status"] == "approved" else "반려"
    emoji = "✅" if row["status"] == "approved" else "❌"
    decider = row.get("decided_by_name") or f"<@{row['decided_by']}>"
    lines = [
        f"{emoji} <@{row['requester_id']}> 님의 '{row['category']}' "
        f"사용 요청이 {verb}되었습니다.",
        f"• 처리자: {decider}",
    ]
    if row["status"] == "rejected" and row.get("reject_reason"):
        lines.append(f"• 반려 사유: {row['reject_reason']}")
    return "\n".join(lines)
