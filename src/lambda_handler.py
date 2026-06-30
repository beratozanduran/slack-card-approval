"""AWS Lambda 진입점 (Function URL → Slack Events/Interactivity).

- create_app()는 모듈 로드 시 1회 실행되어 warm invocation 간 재사용된다.
- lazy listener는 SlackRequestHandler가 같은 Lambda를 비동기 재호출해 실행한다
  (실행 역할에 자기 자신에 대한 lambda:InvokeFunction 권한 필요).
"""
import logging

from slack_bolt.adapter.aws_lambda import SlackRequestHandler

from app import create_app

logging.basicConfig(level=logging.INFO)

SlackRequestHandler.clear_all_log_handlers()

_app = create_app(process_before_response=True)
_handler = SlackRequestHandler(app=_app)


def handler(event, context):
    return _handler.handle(event, context)
