import logging

from slack_bolt import App

from config import load_config
from services.sheets_sync import SheetsSync, open_worksheet
from handlers.command import handle_approval_command
from handlers.view_submission import ack_submission, process_submission, submit_sync
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


def create_app(cfg=None, *, process_before_response=True, use_lazy=True) -> App:
    """DB 없는 서버리스 앱.

    use_lazy=True  : 무거운 작업(게시/시트)을 Bolt lazy listener로 처리해 3초 ack 보장.
                     단, lazy는 같은 Lambda를 자기 호출하므로 실행 역할에
                     lambda:InvokeFunction(self) 권한이 필요하다(Terraform 경로).
    use_lazy=False : 동기 처리(self-invoke 불필요, basic 역할로 충분). 콘솔 수동 배포용.
                     무거운 작업이 3초를 넘으면 Slack 재시도 위험이 있으나 저빈도면 무방.
    모달 오픈은 trigger_id 민감 → 항상 동기.
    """
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

    # 반려 버튼 — 사유 모달 오픈(동기, trigger_id 민감)
    @app.action("reject")
    def _reject(ack, body, client, respond):
        handle_reject_open(
            ack, body, client, respond, approver_user_id=cfg.approver_user_id,
        )

    def _submit_work(body, client):
        process_submission(body, client,
                           approver_user_id=cfg.approver_user_id,
                           log_channel_id=cfg.log_channel_id)

    def _approve_work(body, client):
        handle_approve(body, client,
                       approver_user_id=cfg.approver_user_id,
                       log_channel_id=cfg.log_channel_id, sheets_sync=sheets_sync)

    def _reject_reason_work(body, client):
        handle_reject_reason(body, client,
                            log_channel_id=cfg.log_channel_id, sheets_sync=sheets_sync)

    if use_lazy:
        app.view("approval_submit")(ack=ack_submission, lazy=[_submit_work])
        app.action("approve")(ack=lambda ack: ack(), lazy=[_approve_work])
        app.view("reject_reason_submit")(ack=lambda ack: ack(), lazy=[_reject_reason_work])
    else:
        @app.view("approval_submit")
        def _submit_sync(ack, body, client):
            submit_sync(ack, body, client,
                        approver_user_id=cfg.approver_user_id,
                        log_channel_id=cfg.log_channel_id)

        @app.action("approve")
        def _approve_sync(ack, body, client):
            ack()
            _approve_work(body, client)

        @app.view("reject_reason_submit")
        def _reject_reason_sync(ack, body, client):
            ack()
            _reject_reason_work(body, client)

    logging.getLogger(__name__).info(
        "에듀카드 app created (process_before_response=%s, lazy=%s)",
        process_before_response, use_lazy)
    return app
