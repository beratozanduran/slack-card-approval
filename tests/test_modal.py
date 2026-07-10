from views.modal import build_approval_modal

def test_modal_has_correct_callback_id():
    view = build_approval_modal(prefill_name="Ozan")
    assert view["callback_id"] == "approval_submit"
    assert view["type"] == "modal"

def test_modal_prefills_requester_name():
    view = build_approval_modal(prefill_name="Ozan")
    blocks = view["blocks"]
    name_block = next(b for b in blocks if b["block_id"] == "requester_name")
    assert name_block["element"]["initial_value"] == "Ozan"

def test_modal_has_all_26_categories():
    view = build_approval_modal(prefill_name="x")
    cat_block = next(b for b in view["blocks"] if b["block_id"] == "category")
    assert len(cat_block["element"]["options"]) == 26

def test_modal_has_optional_note_field():
    view = build_approval_modal(prefill_name="x")
    note_block = next(b for b in view["blocks"] if b["block_id"] == "note")
    assert note_block["optional"] is True
    assert note_block["element"]["multiline"] is True
