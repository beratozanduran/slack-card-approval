from slack_bolt import App

from config import load_config
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.command import handle_approval_command
from handlers.view_submission import handle_view_submission


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
    return app
