from views.approval_card import build_approval_card, build_decided_card

def _sample_row():
    return {
        "id": 42, "requester_name": "Ozan", "category": "점심식비",
        "amount": 12000, "used_date": "2026-05-28",
        "merchant": "김밥천국", "created_at": "2026-05-28T14:32:00",
        "status": "pending",
    }

def test_pending_card_has_buttons():
    blocks = build_approval_card(_sample_row())
    action_block = next(b for b in blocks if b["type"] == "actions")
    actions = action_block["elements"]
    assert {a["action_id"] for a in actions} == {"approve", "reject"}
    assert all(a["value"] == "42" for a in actions)

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
