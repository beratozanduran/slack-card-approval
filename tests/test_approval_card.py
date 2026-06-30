import json

from views.approval_card import build_approval_card, build_decided_card

def _sample_row():
    return {
        "id": "260528-143200", "requester_id": "U_REQ",
        "requester_name": "Ozan", "category": "점심식비",
        "amount": 12000, "used_date": "2026-05-28",
        "merchant": "김밥천국", "created_at": "2026-05-28 14:32:00",
        "channel_msg_ts": "100.0", "status": "pending",
    }

def test_pending_card_has_buttons():
    row = _sample_row()
    blocks = build_approval_card(row)
    action_block = next(b for b in blocks if b["type"] == "actions")
    actions = action_block["elements"]
    assert {a["action_id"] for a in actions} == {"approve", "reject"}
    # DB가 없으므로 버튼 value에 신청 데이터(JSON)가 실려야 함
    for a in actions:
        data = json.loads(a["value"])
        assert data["id"] == "260528-143200"
        assert data["amount"] == 12000
        assert data["channel_msg_ts"] == "100.0"

def test_pending_card_shows_amount_formatted():
    blocks = build_approval_card(_sample_row())
    text = "".join(str(b) for b in blocks)
    assert "12,000원" in text

def test_decided_card_has_no_buttons():
    row = {**_sample_row(), "status": "approved",
           "decided_by": "U2", "decided_at": "2026-05-28T14:33:00"}
    blocks = build_decided_card(row)
    assert not any(b["type"] == "actions" for b in blocks)
    text = "".join(str(b) for b in blocks)
    assert "승인됨" in text or "✅" in text
