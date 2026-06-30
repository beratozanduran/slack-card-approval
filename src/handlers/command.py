from views.modal import build_approval_modal


def handle_approval_command(ack, body, client):
    ack()
    user_info = client.users_info(user=body["user_id"])
    profile = user_info["user"]["profile"]
    # 표시이름(NxtCloud_Ozan)이 아니라 성명(real_name, 예: Ozan)을 우선 채운다.
    name = profile.get("real_name") or profile.get("display_name") or ""
    client.views_open(
        trigger_id=body["trigger_id"],
        view=build_approval_modal(prefill_name=name),
    )
