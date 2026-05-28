from slack_bolt import App

from config import load_config
from handlers.command import handle_approval_command


def create_app(cfg=None) -> App:
    cfg = cfg or load_config()
    app = App(token=cfg.bot_token, signing_secret=cfg.signing_secret)
    app.command("/approval")(handle_approval_command)
    return app
