"""AWS Lambda 진입점 (Function URL → Slack Events/Interactivity).

- create_app()는 모듈 로드 시 1회 실행되어 warm invocation 간 재사용된다.
- lazy listener는 SlackRequestHandler가 같은 Lambda를 비동기 재호출해 실행한다
  (실행 역할에 자기 자신에 대한 lambda:InvokeFunction 권한 필요).
"""
import logging
import os

from slack_bolt.adapter.aws_lambda import SlackRequestHandler

from app import create_app

logging.basicConfig(level=logging.INFO)

SlackRequestHandler.clear_all_log_handlers()

# 콘솔 수동 배포(basic 역할, self-invoke 없음)에서는 EDUKARD_USE_LAZY=false 로 동기 모드.
# Terraform 배포(self-invoke 권한 있음)에서는 기본값(lazy)으로 둔다.
_use_lazy = os.environ.get("EDUKARD_USE_LAZY", "true").lower() != "false"

_app = create_app(process_before_response=True, use_lazy=_use_lazy)
_handler = SlackRequestHandler(app=_app)


def handler(event, context):
    return _handler.handle(event, context)
