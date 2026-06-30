from unittest.mock import MagicMock
from handlers.command import handle_approval_command


def test_opens_modal_with_prefill_name():
    ack = MagicMock()
    client = MagicMock()
    client.users_info.return_value = {"user": {"profile": {"display_name": "Ozan"}}}
    body = {"trigger_id": "t1", "user_id": "U1"}
    handle_approval_command(ack=ack, body=body, client=client)
    ack.assert_called_once()
    args = client.views_open.call_args.kwargs
    assert args["trigger_id"] == "t1"
    name_block = next(
        b for b in args["view"]["blocks"] if b["block_id"] == "requester_name"
    )
    assert name_block["element"]["initial_value"] == "Ozan"


def test_prefers_real_name_over_display_name():
    ack = MagicMock()
    client = MagicMock()
    client.users_info.return_value = {
        "user": {"profile": {"real_name": "Ozan", "display_name": "NxtCloud_Ozan"}}
    }
    handle_approval_command(ack=ack, body={"trigger_id": "t", "user_id": "U1"},
                            client=client)
    args = client.views_open.call_args.kwargs
    name_block = next(
        b for b in args["view"]["blocks"] if b["block_id"] == "requester_name"
    )
    # 성명(real_name)이 우선, 표시이름은 무시
    assert name_block["element"]["initial_value"] == "Ozan"
