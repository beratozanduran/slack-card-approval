import json
import logging

from views.approval_card import build_decided_card, build_thread_result_text
from views.modal import build_reject_reason_modal
from services.approval_repo import ApprovalNotPending
from services.sheets_retry import enqueue

log = logging.getLogger(__name__)


def _decider_name(client, user_id: str) -> str:
    """Sheets/카드 가독성을 위해 승인자 ID 대신 표시 이름을 얻는다."""
    try:
        profile = client.users_info(user=user_id)["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        log.exception("승인자 이름 조회 실패 (%s)", user_id)
        return user_id


def _finalize_decision(*, client, conn, row, log_channel_id,
                       approver_channel, approver_msg_ts, sheets_sync):
    """승인/반려 공통 후처리. 각 외부 호출을 격리해 한 단계 실패가
    다음 단계를 막지 않도록 한다. 결과는 DM이 아닌 공개 스레드에 남긴다."""
    decided_blocks = build_decided_card(dict(row))

    # 승인자 DM 카드를 결과로 갱신
    try:
        client.chat_update(
            channel=approver_channel, ts=approver_msg_ts,
            blocks=decided_blocks,
            text=f"카드 승인 요청 #{row['id']} {row['status']}",
        )
    except Exception:
        log.exception("승인자 카드 chat_update 실패 (#%s)", row["id"])

    # 로그 채널 부모 카드(대기중)를 결과로 갱신
    if row["channel_msg_ts"]:
        try:
            client.chat_update(
                channel=log_channel_id, ts=row["channel_msg_ts"],
                blocks=decided_blocks,
                text=f"카드 사용 승인 요청 #{row['id']} 처리 결과",
            )
        except Exception:
            log.exception("채널 부모 카드 chat_update 실패 (#%s)", row["id"])

        # 신청자에게는 DM이 아니라 부모 메시지의 스레드 답글로 알린다(투명성).
        try:
            client.chat_postMessage(
                channel=log_channel_id, thread_ts=row["channel_msg_ts"],
                text=build_thread_result_text(dict(row)),
            )
        except Exception:
            log.exception("스레드 결과 답글 실패 (#%s)", row["id"])

    try:
        sheets_sync(dict(row))
    except Exception as e:
        log.error("Sheets sync 즉시 실패, 큐 적재: %s", e)
        enqueue(conn, row["id"], str(e))


def handle_decision(*, ack, body, client, repo, conn, approver_user_id,
                    log_channel_id, sheets_sync, respond=None):
    """승인/반려 버튼. 승인은 즉시 처리, 반려는 사유 입력 모달을 띄운다."""
    ack()
    user_id = body["user"]["id"]
    if user_id != approver_user_id:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이 요청을 처리할 권한이 없습니다."})
        return

    action = body["actions"][0]
    approval_id = int(action["value"])

    # 반려: 사유를 받아야 하므로 모달을 띄우고, 실제 처리는 모달 제출에서 한다.
    if action["action_id"] == "reject":
        try:
            client.views_open(
                trigger_id=body["trigger_id"],
                view=build_reject_reason_modal(
                    approval_id=approval_id,
                    approver_msg_ts=body["message"]["ts"],
                    channel=body["channel"]["id"],
                ),
            )
        except Exception:
            log.exception("반려 사유 모달 오픈 실패 (#%s)", approval_id)
        return

    # 승인: 즉시 처리
    name = _decider_name(client, user_id)
    try:
        row = repo.decide(approval_id, "approved", user_id,
                          body["message"]["ts"], decided_by_name=name)
    except ApprovalNotPending:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이미 처리된 요청입니다."})
        return

    _finalize_decision(
        client=client, conn=conn, row=row, log_channel_id=log_channel_id,
        approver_channel=body["channel"]["id"],
        approver_msg_ts=body["message"]["ts"], sheets_sync=sheets_sync,
    )


def handle_reject_reason(*, ack, body, client, repo, conn,
                         log_channel_id, sheets_sync):
    """반려 사유 모달 제출 — 사유와 함께 반려를 확정하고 후처리한다."""
    ack()
    meta = json.loads(body["view"]["private_metadata"])
    approval_id = meta["approval_id"]
    reason = (body["view"]["state"]["values"]
              ["reject_reason"]["value"]["value"])
    user_id = body["user"]["id"]
    name = _decider_name(client, user_id)

    try:
        row = repo.decide(approval_id, "rejected", user_id,
                          meta["approver_msg_ts"], decided_by_name=name,
                          reject_reason=reason)
    except ApprovalNotPending:
        log.info("반려 모달 제출 시 이미 처리됨 (#%s)", approval_id)
        return

    _finalize_decision(
        client=client, conn=conn, row=row, log_channel_id=log_channel_id,
        approver_channel=meta["channel"],
        approver_msg_ts=meta["approver_msg_ts"], sheets_sync=sheets_sync,
    )
