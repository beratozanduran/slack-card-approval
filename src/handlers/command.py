from views.modal import build_approval_modal


def handle_approval_command(ack, body, client):
    ack()
    user_info = client.users_info(user=body["user_id"])
    profile = user_info["user"]["profile"]
    name = profile.get("display_name") or profile.get("real_name") or ""
    client.views_open(
        trigger_id=body["trigger_id"],
        view=build_approval_modal(prefill_name=name),
    )
