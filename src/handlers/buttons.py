from views.approval_card import build_decided_card
from services.approval_repo import ApprovalNotPending

def handle_decision(*, ack, body, client, repo, approver_user_id,
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

    decided_blocks = build_decided_card(dict(row))
    client.chat_update(
        channel=body["channel"]["id"], ts=msg_ts,
        blocks=decided_blocks,
        text=f"카드 승인 요청 #{row['id']} {decision}",
    )
    client.chat_postMessage(
        channel=log_channel_id, blocks=decided_blocks,
        text=f"카드 승인 요청 #{row['id']} 처리 결과",
    )
    client.chat_postMessage(
        channel=row["requester_id"],
        text=(f"카드 승인 요청 #{row['id']}이(가) "
              f"{'승인' if decision == 'approved' else '반려'}되었습니다."),
    )
    sheets_sync(row)
