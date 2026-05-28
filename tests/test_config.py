import pytest
from config import load_config, ConfigError


def test_load_config_success(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-x")
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "s")
    monkeypatch.setenv("APPROVER_USER_ID", "U1")
    monkeypatch.setenv("LOG_CHANNEL_ID", "C1")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sh")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "/tmp/sa.json")
    monkeypatch.setenv("DATABASE_PATH", "/tmp/x.db")
    cfg = load_config()
    assert cfg.approver_user_id == "U1"
    assert cfg.log_channel_id == "C1"


def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="SLACK_BOT_TOKEN"):
        load_config()
