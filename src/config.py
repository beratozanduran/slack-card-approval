import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


REQUIRED = [
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "APPROVER_USER_ID",
    "LOG_CHANNEL_ID",
    "GOOGLE_SHEETS_ID",
    "GOOGLE_SERVICE_ACCOUNT_JSON",
    "DATABASE_PATH",
]


@dataclass(frozen=True)
class Config:
    bot_token: str
    signing_secret: str
    app_token: str | None
    approver_user_id: str
    log_channel_id: str
    sheets_id: str
    service_account_json: str
    database_path: str


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
        service_account_json=os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"],
        database_path=os.environ["DATABASE_PATH"],
    )
