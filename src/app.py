import logging

from slack_bolt import App

from config import load_config
from services.sheets_sync import SheetsSync, open_worksheet
from handlers.command import handle_approval_command
from handlers.view_submission import ack_submission, process_submission
from handlers.buttons import (
    handle_approve, handle_reject_open, handle_reject_reason,
)


class _LazySheets:
    """Google 인증/시트 오픈을 첫 기록 시점까지 미뤄 cold start ack를 빠르게 유지한다."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._sync = None

    def __call__(self, row):
        if self._sync is None:
            ws = open_worksheet(self.cfg.service_account_json, self.cfg.sheets_id)
            self._sync = SheetsSync(ws)
        self._sync(row)


def create_app(cfg=None, *, process_before_response=True) -> App:
    """DB 없는 서버리스 앱. 무거운 작업(게시/시트 기록)은 lazy listener로 처리해
    3초 ack를 보장한다. 모달 오픈은 trigger_id 민감하므로 동기 처리."""
    cfg = cfg or load_config()
    app = App(
        token=cfg.bot_token, signing_secret=cfg.signing_secret,
        process_before_response=process_before_response,
    )
    sheets_sync = _LazySheets(cfg)

    # /에듀카드 — 신청 모달 오픈(동기, trigger_id 민감)
    @app.command("/에듀카드")
    def _cmd(ack, body, client):
        handle_approval_command(ack, body, client)

    # 모달 제출 — 검증/ack는 동기(에러를 모달에 표시), 게시는 lazy
    def _submit_work(body, client):
        process_submission(
            body, client,
            approver_user_id=cfg.approver_user_id,
            log_channel_id=cfg.log_channel_id,
        )

    app.view("approval_submit")(ack=ack_submission, lazy=[_submit_work])

    # 승인 버튼 — ack 즉시, 처리(시트 기록 포함)는 lazy
    def _approve_work(body, client):
        handle_approve(
            body, client,
            approver_user_id=cfg.approver_user_id,
            log_channel_id=cfg.log_channel_id,
            sheets_sync=sheets_sync,
        )

    app.action("approve")(ack=lambda ack: ack(), lazy=[_approve_work])

    # 반려 버튼 — 사유 모달 오픈(동기, trigger_id 민감)
    @app.action("reject")
    def _reject(ack, body, client, respond):
        handle_reject_open(
            ack, body, client, respond, approver_user_id=cfg.approver_user_id,
        )

    # 반려 사유 제출 — ack 즉시, 처리는 lazy
    def _reject_reason_work(body, client):
        handle_reject_reason(
            body, client,
            log_channel_id=cfg.log_channel_id, sheets_sync=sheets_sync,
        )

    app.view("reject_reason_submit")(
        ack=lambda ack: ack(), lazy=[_reject_reason_work],
    )

    logging.getLogger(__name__).info("에듀카드 app created (process_before_response=%s)",
                                     process_before_response)
    return app
