from datetime import date
from views.approval_card import build_approval_card

def _extract(values: dict, block_id: str, key: str):
    return values[block_id]["value"][key]

def handle_view_submission(*, ack, body, client, repo, approver_user_id):
    values = body["view"]["state"]["values"]
    requester_name = _extract(values, "requester_name", "value")
    category = values["category"]["value"]["selected_option"]["value"]
    amount = int(_extract(values, "amount", "value"))
    used_date = date.fromisoformat(
        values["used_date"]["value"]["selected_date"]
    )
    merchant = _extract(values, "merchant", "value")
    ack()  # 모달 닫기
    row = repo.create_pending(
        requester_id=body["user"]["id"],
        requester_name=requester_name,
        category=category, amount=amount,
        used_date=used_date, merchant=merchant,
    )
    client.chat_postMessage(
        channel=approver_user_id,
        blocks=build_approval_card(dict(row)),
        text=f"카드 승인 요청 #{row['id']}",
    )
