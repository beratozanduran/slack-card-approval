import logging
from datetime import date

from clock import now_kst_str, now_kst_ref
from views.approval_card import build_approval_card, build_pending_channel_card

log = logging.getLogger(__name__)


def _extract(values: dict, block_id: str, key: str):
    return values[block_id]["value"][key]


def _validate(values: dict) -> tuple[dict, dict]:
    """모달 입력을 검증한다. (errors, parsed)를 반환한다."""
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


def ack_submission(ack, body):
    """3초 안에 응답: 검증 실패면 에러를 모달에 표시, 통과면 모달을 닫는다.

    (실제 게시는 lazy listener process_submission 에서 한다.)
    """
    errors, _ = _validate(body["view"]["state"]["values"])
    if errors:
        ack(response_action="errors", errors=errors)
    else:
        ack()


def _row_from_values(body) -> dict:
    """모달 입력으로 신청 데이터(row)를 만든다. DB가 없으므로 이 dict가
    Slack 버튼 value에 실려 승인/반려 시점까지 상태를 운반한다."""
    values = body["view"]["state"]["values"]
    _, parsed = _validate(values)
    return {
        "id": now_kst_ref(),
        "requester_id": body["user"]["id"],
        "requester_name": _extract(values, "requester_name", "value"),
        "category": values["category"]["value"]["selected_option"]["value"],
        "amount": parsed["amount"],
        "used_date": parsed["used_date"].isoformat(),
        "merchant": _extract(values, "merchant", "value"),
        "created_at": now_kst_str(),
        "channel_msg_ts": None,
    }


def _notify_requester_error(client, requester_id):
    try:
        client.chat_postMessage(
            channel=requester_id,
            text="신청 접수 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )
    except Exception:
        log.exception("신청자 재시도 안내 DM도 실패")


def process_submission(body, client, *, approver_user_id, log_channel_id):
    """신청을 게시한다(검증은 ack 단계에서 통과한 상태).

    1) 로그 채널에 '대기중' 카드를 올려 스레드 기준점(parent ts)을 만든다.
    2) 승인자 DM에 승인/반려 버튼 카드를 보낸다. 버튼 value에 신청 데이터를 실어
       이후 결정 시점까지 상태를 운반한다(별도 DB 없음).
    """
    row = _row_from_values(body)

    try:
        posted = client.chat_postMessage(
            channel=log_channel_id,
            blocks=build_pending_channel_card(row),
            text=f"에듀카드 사용 요청 {row['id']} (대기중)",
        )
        row["channel_msg_ts"] = posted["ts"]
    except Exception as e:
        log.error("로그 채널 게시 실패 (%s): %s", row["id"], e)
        _notify_requester_error(client, row["requester_id"])
        return

    try:
        client.chat_postMessage(
            channel=approver_user_id,
            blocks=build_approval_card(row),
            text=f"에듀카드 사용 요청 {row['id']}",
        )
    except Exception as e:
        log.error("승인자 DM 실패, 롤백 (%s): %s", row["id"], e)
        try:
            client.chat_delete(channel=log_channel_id, ts=row["channel_msg_ts"])
        except Exception:
            log.exception("채널 대기중 카드 삭제 실패 (%s)", row["id"])
        _notify_requester_error(client, row["requester_id"])
