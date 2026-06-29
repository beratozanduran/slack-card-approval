import logging
from datetime import date

from views.approval_card import build_approval_card, build_pending_channel_card

log = logging.getLogger(__name__)


def _extract(values: dict, block_id: str, key: str):
    return values[block_id]["value"][key]


def _validate(values: dict) -> tuple[dict, dict]:
    """모달 입력을 검증한다. (errors, parsed)를 반환한다.

    errors는 {block_id: 메시지} 형식으로, 비어 있지 않으면
    ack(response_action="errors", errors=...)로 모달에 표시한다.
    """
    errors: dict = {}
    parsed: dict = {}

    try:
        amount = int(_extract(values, "amount", "value"))
        if amount <= 0:
            errors["amount"] = "금액은 1원 이상이어야 합니다."
        else:
            parsed["amount"] = amount
    except (ValueError, TypeError, KeyError):
        errors["amount"] = "금액을 숫자로 입력해 주세요."

    try:
        used_date = date.fromisoformat(
            values["used_date"]["value"]["selected_date"]
        )
        if used_date > date.today():
            errors["used_date"] = "미래 날짜는 신청할 수 없습니다."
        else:
            parsed["used_date"] = used_date
    except (ValueError, TypeError, KeyError):
        errors["used_date"] = "사용 날짜를 선택해 주세요."

    return errors, parsed


def _notify_requester_error(client, requester_id):
    try:
        client.chat_postMessage(
            channel=requester_id,
            text="신청 접수 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )
    except Exception:
        log.exception("신청자 재시도 안내 DM도 실패")


def handle_view_submission(*, ack, body, client, repo, approver_user_id,
                           log_channel_id):
    values = body["view"]["state"]["values"]

    errors, parsed = _validate(values)
    if errors:
        # I6: 검증 실패 시 모달을 닫지 않고 에러를 표시한다.
        ack(response_action="errors", errors=errors)
        return

    requester_name = _extract(values, "requester_name", "value")
    category = values["category"]["value"]["selected_option"]["value"]
    merchant = _extract(values, "merchant", "value")
    ack()  # 모달 닫기

    row = repo.create_pending(
        requester_id=body["user"]["id"],
        requester_name=requester_name,
        category=category, amount=parsed["amount"],
        used_date=parsed["used_date"], merchant=merchant,
    )

    # 투명성: 신청 즉시 로그 채널에 '대기중' 카드를 게시한다. 이 메시지가
    # 스레드 기준점이 되어, 승인/반려 결과가 같은 스레드에 공개로 남는다.
    try:
        posted = client.chat_postMessage(
            channel=log_channel_id,
            blocks=build_pending_channel_card(dict(row)),
            text=f"카드 사용 승인 요청 #{row['id']} (대기중)",
        )
        repo.set_channel_msg_ts(row["id"], posted["ts"])
    except Exception as e:
        log.error("로그 채널 게시 실패, pending row 삭제 (#%s): %s", row["id"], e)
        repo.delete(row["id"])
        _notify_requester_error(client, body["user"]["id"])
        return

    # I2: 승인자 DM이 실패하면 좀비 pending row가 남으므로 채널 카드와 함께
    # 정리하고 신청자에게 재시도를 안내한다.
    try:
        client.chat_postMessage(
            channel=approver_user_id,
            blocks=build_approval_card(dict(row)),
            text=f"카드 승인 요청 #{row['id']}",
        )
    except Exception as e:
        log.error("승인자 DM 실패, 롤백 (#%s): %s", row["id"], e)
        try:
            client.chat_delete(channel=log_channel_id, ts=posted["ts"])
        except Exception:
            log.exception("채널 대기중 카드 삭제 실패 (#%s)", row["id"])
        repo.delete(row["id"])
        _notify_requester_error(client, body["user"]["id"])
