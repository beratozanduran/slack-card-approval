import logging

from views.approval_card import build_decided_card
from services.approval_repo import ApprovalNotPending
from services.sheets_retry import enqueue

log = logging.getLogger(__name__)


def handle_decision(*, ack, body, client, repo, conn, approver_user_id,
                    log_channel_id, sheets_sync, respond=None):
    ack()
    user_id = body["user"]["id"]
    if user_id != approver_user_id:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이 요청을 처리할 권한이 없습니다."})
        return

    action = body["actions"][0]
    approval_id = int(action["value"])
    decision = "approved" if action["action_id"] == "approve" else "rejected"
    msg_ts = body["message"]["ts"]

    try:
        row = repo.decide(approval_id, decision, user_id, msg_ts)
    except ApprovalNotPending:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이미 처리된 요청입니다."})
        return

    # I1: 각 외부 호출을 격리해 앞 단계 실패가 뒤 단계를 막지 않도록 한다.
    decided_blocks = build_decided_card(dict(row))
    try:
        client.chat_update(
            channel=body["channel"]["id"], ts=msg_ts,
            blocks=decided_blocks,
            text=f"카드 승인 요청 #{row['id']} {decision}",
        )
    except Exception:
        log.exception("승인자 카드 chat_update 실패 (#%s)", row["id"])

    try:
        client.chat_postMessage(
            channel=log_channel_id, blocks=decided_blocks,
            text=f"카드 승인 요청 #{row['id']} 처리 결과",
        )
    except Exception:
        log.exception("로그 채널 postMessage 실패 (#%s)", row["id"])

    # I5: 신청자 결과 DM에 금액·가맹점 등 맥락을 추가한다.
    verb = "승인" if decision == "approved" else "반려"
    try:
        client.chat_postMessage(
            channel=row["requester_id"],
            text=(f"💳 카드 승인 요청 #{row['id']}이(가) {verb}되었습니다.\n"
                  f"• 용도: {row['category']}\n"
                  f"• 금액: {row['amount']:,}원\n"
                  f"• 가맹점: {row['merchant']}\n"
                  f"• 사용일: {row['used_date']}"),
        )
    except Exception:
        log.exception("신청자 결과 DM 실패 (#%s)", row["id"])

    try:
        sheets_sync(dict(row))
    except Exception as e:
        log.error("Sheets sync 즉시 실패, 큐 적재: %s", e)
        enqueue(conn, row["id"], str(e))
