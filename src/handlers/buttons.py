import json
import logging
import time

from clock import now_kst_str
from views.approval_card import build_decided_card, build_thread_result_text
from views.modal import build_reject_reason_modal

log = logging.getLogger(__name__)


def _decider_name(client, user_id: str) -> str:
    """Sheets/카드 가독성을 위해 승인자 ID 대신 표시 이름을 얻는다."""
    try:
        profile = client.users_info(user=user_id)["user"]["profile"]
        return profile.get("display_name") or profile.get("real_name") or user_id
    except Exception:
        log.exception("승인자 이름 조회 실패 (%s)", user_id)
        return user_id


def _ephemeral(client, body, text):
    try:
        client.chat_postEphemeral(
            channel=body["channel"]["id"], user=body["user"]["id"], text=text
        )
    except Exception:
        log.exception("ephemeral 응답 실패")


def _sync_sheets(sheets_sync, row, client, log_channel_id, attempts=3):
    """DB가 없으므로 영속 retry 큐 대신 인라인 재시도 + 실패 시 스레드 경고."""
    last = None
    for i in range(attempts):
        try:
            sheets_sync(row)
            return
        except Exception as e:
            last = e
            log.error("Sheets 기록 실패 (%s, %s/%s): %s",
                      row.get("id"), i + 1, attempts, e)
            if i < attempts - 1:
                time.sleep(0.5)
    if row.get("channel_msg_ts"):
        try:
            client.chat_postMessage(
                channel=log_channel_id, thread_ts=row["channel_msg_ts"],
                text=f"⚠️ Google Sheets 기록 실패 — 수동 확인이 필요합니다. (사유: {last})",
            )
        except Exception:
            log.exception("Sheets 실패 경고 게시도 실패 (%s)", row.get("id"))


def _finalize_decision(*, client, row, log_channel_id,
                       approver_channel, approver_msg_ts, sheets_sync):
    """승인/반려 공통 후처리. 각 외부 호출을 격리하고 결과는 공개 스레드에 남긴다."""
    decided_blocks = build_decided_card(row)

    try:
        client.chat_update(
            channel=approver_channel, ts=approver_msg_ts,
            blocks=decided_blocks,
            text=f"에듀카드 사용 요청 #{row['id']} {row['status']}",
        )
    except Exception:
        log.exception("승인자 카드 chat_update 실패 (%s)", row["id"])

    if row.get("channel_msg_ts"):
        try:
            client.chat_update(
                channel=log_channel_id, ts=row["channel_msg_ts"],
                blocks=decided_blocks,
                text=f"에듀카드 사용 요청 #{row['id']} 처리 결과",
            )
        except Exception:
            log.exception("채널 부모 카드 chat_update 실패 (%s)", row["id"])

        # 신청자에게는 DM이 아니라 부모 메시지의 스레드 답글로 알린다(투명성).
        try:
            client.chat_postMessage(
                channel=log_channel_id, thread_ts=row["channel_msg_ts"],
                text=build_thread_result_text(row),
            )
        except Exception:
            log.exception("스레드 결과 답글 실패 (%s)", row["id"])

    _sync_sheets(sheets_sync, row, client, log_channel_id)


def handle_approve(body, client, *, approver_user_id, log_channel_id, sheets_sync):
    """승인 버튼의 실제 처리(lazy). 신청 데이터는 버튼 value(JSON)에서 복원한다."""
    user_id = body["user"]["id"]
    if user_id != approver_user_id:
        _ephemeral(client, body, "이 요청을 처리할 권한이 없습니다.")
        return

    row = json.loads(body["actions"][0]["value"])
    row.update(
        status="approved", decided_by=user_id,
        decided_by_name=_decider_name(client, user_id),
        reject_reason=None, decided_at=now_kst_str(),
    )
    _finalize_decision(
        client=client, row=row, log_channel_id=log_channel_id,
        approver_channel=body["channel"]["id"],
        approver_msg_ts=body["message"]["ts"], sheets_sync=sheets_sync,
    )


def handle_reject_open(ack, body, client, respond=None, *, approver_user_id):
    """반려 버튼: 사유 입력 모달을 띄운다(trigger_id 민감 → 동기 처리)."""
    ack()
    if body["user"]["id"] != approver_user_id:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이 요청을 처리할 권한이 없습니다."})
        return
    row = json.loads(body["actions"][0]["value"])
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=build_reject_reason_modal(
                row=row, approver_msg_ts=body["message"]["ts"],
                channel=body["channel"]["id"],
            ),
        )
    except Exception:
        log.exception("반려 사유 모달 오픈 실패 (%s)", row.get("id"))


def handle_reject_reason(body, client, *, log_channel_id, sheets_sync):
    """반려 사유 모달 제출의 실제 처리(lazy)."""
    meta = json.loads(body["view"]["private_metadata"])
    row = meta["row"]
    reason = (body["view"]["state"]["values"]
              ["reject_reason"]["value"]["value"])
    user_id = body["user"]["id"]
    row.update(
        status="rejected", decided_by=user_id,
        decided_by_name=_decider_name(client, user_id),
        reject_reason=reason, decided_at=now_kst_str(),
    )
    _finalize_decision(
        client=client, row=row, log_channel_id=log_channel_id,
        approver_channel=meta["channel"], approver_msg_ts=meta["approver_msg_ts"],
        sheets_sync=sheets_sync,
    )
