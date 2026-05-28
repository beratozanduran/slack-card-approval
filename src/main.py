import os
import logging
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
load_dotenv()

from app import create_app
from config import load_config


def main():
    cfg = load_config()
    app = create_app(cfg)
    if cfg.app_token:
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        SocketModeHandler(app, cfg.app_token).start()
    else:
        app.start(port=int(os.environ.get("PORT", 3000)))


if __name__ == "__main__":
    main()
