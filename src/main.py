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
    # 로컬(Socket Mode/내장 HTTP)에서는 동기 ack가 자연스럽다. Lambda 진입점은
    # lambda_handler.py에서 process_before_response=True로 별도 생성한다.
    app = create_app(cfg, process_before_response=False)
    if cfg.app_token:
        from slack_bolt.adapter.socket_mode import SocketModeHandler
        SocketModeHandler(app, cfg.app_token).start()
    else:
        app.start(port=int(os.environ.get("PORT", 3000)))


if __name__ == "__main__":
    main()
