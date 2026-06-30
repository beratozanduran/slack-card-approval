import os
from dataclasses import dataclass

from secrets_loader import resolve_service_account_json


class ConfigError(RuntimeError):
    pass


# DB가 없는 서버리스 구조. DATABASE_PATH 제거.
REQUIRED = [
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "APPROVER_USER_ID",
    "LOG_CHANNEL_ID",
    "GOOGLE_SHEETS_ID",
]


@dataclass(frozen=True)
class Config:
    bot_token: str
    signing_secret: str
    app_token: str | None          # 로컬 Socket Mode 개발용. Lambda(HTTP)에선 미사용.
    approver_user_id: str
    log_channel_id: str
    sheets_id: str
    service_account_json: str       # 파일 경로(로컬) 또는 SSM에서 받은 /tmp 경로(Lambda)


def load_config() -> Config:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        raise ConfigError(f"필수 환경변수 누락: {', '.join(missing)}")
    return Config(
        bot_token=os.environ["SLACK_BOT_TOKEN"],
        signing_secret=os.environ["SLACK_SIGNING_SECRET"],
        app_token=os.environ.get("SLACK_APP_TOKEN"),
        approver_user_id=os.environ["APPROVER_USER_ID"],
        log_channel_id=os.environ["LOG_CHANNEL_ID"],
        sheets_id=os.environ["GOOGLE_SHEETS_ID"],
        service_account_json=resolve_service_account_json(),
    )
