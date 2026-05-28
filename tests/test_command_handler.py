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
