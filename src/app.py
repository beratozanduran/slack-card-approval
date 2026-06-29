import logging
import threading
import time

from slack_bolt import App

from config import load_config
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from services.sheets_sync import SheetsSync, open_worksheet
from services.sheets_retry import drain_once
from handlers.command import handle_approval_command
from handlers.view_submission import handle_view_submission
from handlers.buttons import handle_decision, handle_reject_reason


def _retry_worker(conn, repo, sheets_sync_fn):
    while True:
        try:
            drain_once(conn, repo, sheets_sync_fn)
        except Exception as e:
            logging.error("retry worker 오류: %s", e)
        time.sleep(300)  # 5분


def create_app(cfg=None) -> App:
    cfg = cfg or load_config()
    conn = connect(cfg.database_path)
    init_schema(conn)
    repo = ApprovalRepo(conn)
    app = App(token=cfg.bot_token, signing_secret=cfg.signing_secret)
    app.command("/카드결재")(handle_approval_command)

    @app.view("approval_submit")
    def _on_submit(ack, body, client):
        handle_view_submission(
            ack=ack, body=body, client=client,
            repo=repo, approver_user_id=cfg.approver_user_id,
            log_channel_id=cfg.log_channel_id,
        )

    try:
        ws = open_worksheet(cfg.service_account_json, cfg.sheets_id)
        sheets_sync_fn = SheetsSync(ws)
    except Exception as e:
        logging.error(
            "Sheets 초기화 실패 — 모든 동기화는 큐로 적재됩니다: %s", e
        )

        def sheets_sync_fn(row):
            raise RuntimeError("sheets unavailable at startup")

    @app.action("approve")
    @app.action("reject")
    def _on_decision(ack, body, client, respond):
        handle_decision(
            ack=ack, body=body, client=client, repo=repo, conn=conn,
            approver_user_id=cfg.approver_user_id,
            log_channel_id=cfg.log_channel_id,
            sheets_sync=sheets_sync_fn,
            respond=respond,
        )

    @app.view("reject_reason_submit")
    def _on_reject_reason(ack, body, client):
        handle_reject_reason(
            ack=ack, body=body, client=client, repo=repo, conn=conn,
            log_channel_id=cfg.log_channel_id,
            sheets_sync=sheets_sync_fn,
        )

    t = threading.Thread(
        target=_retry_worker,
        args=(conn, repo, sheets_sync_fn),
        daemon=True,
    )
    t.start()
    return app
