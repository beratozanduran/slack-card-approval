from slack_bolt import App

from config import load_config
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from services.sheets_sync import SheetsSync, open_worksheet
from handlers.command import handle_approval_command
from handlers.view_submission import handle_view_submission
from handlers.buttons import handle_decision


def create_app(cfg=None) -> App:
    cfg = cfg or load_config()
    conn = connect(cfg.database_path)
    init_schema(conn)
    repo = ApprovalRepo(conn)
    app = App(token=cfg.bot_token, signing_secret=cfg.signing_secret)
    app.command("/approval")(handle_approval_command)

    @app.view("approval_submit")
    def _on_submit(ack, body, client):
        handle_view_submission(
            ack=ack, body=body, client=client,
            repo=repo, approver_user_id=cfg.approver_user_id,
        )

    ws = open_worksheet(cfg.service_account_json, cfg.sheets_id)
    sheets_sync_fn = SheetsSync(ws)

    @app.action("approve")
    @app.action("reject")
    def _on_decision(ack, body, client, respond):
        handle_decision(
            ack=ack, body=body, client=client, repo=repo,
            approver_user_id=cfg.approver_user_id,
            log_channel_id=cfg.log_channel_id,
            sheets_sync=sheets_sync_fn,
            respond=respond,
        )
    return app
