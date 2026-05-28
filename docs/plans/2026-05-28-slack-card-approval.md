# 법인카드 승인 앱 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Slack 슬래시 커맨드(`/approval`)로 법인카드 사용 승인을 신청·승인·기록(SQLite + 채널 + Google Sheets)하는 단일 승인자 앱을 만든다.

**Architecture:** Slack Bolt for Python 앱 한 프로세스(Docker 단일 컨테이너). 핸들러는 모달 제출과 버튼 클릭을 처리하고 결과를 SQLite·`#카드승인-로그` 채널·Google Sheets 세 곳에 분배한다. Sheets 실패는 큐에 적재 후 백그라운드 재시도.

**Tech Stack:** Python 3.11+, `slack-bolt`, `sqlite3`(표준 라이브러리), `gspread` + `google-auth`, `pytest` + `pytest-mock`, Docker

**참고**: 설계 문서는 `docs/plans/2026-05-28-slack-card-approval-design.md` 참조

---

## Task 1: 프로젝트 스캐폴딩

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md` (한 줄만), `src/__init__.py`, `tests/__init__.py`

**Step 1: pyproject.toml 작성**

```toml
[project]
name = "slack-card-approval"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "slack-bolt>=1.18",
  "gspread>=6.0",
  "google-auth>=2.28",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

**Step 2: .gitignore 작성**

```
__pycache__/
*.pyc
.venv/
.env
data/
secrets/
*.db
.pytest_cache/
```

**Step 3: .env.example 작성**

```
SLACK_BOT_TOKEN=xoxb-REPLACE-ME
SLACK_SIGNING_SECRET=REPLACE-ME
SLACK_APP_TOKEN=xapp-REPLACE-ME   # Socket Mode 사용 시
APPROVER_USER_ID=U01ABCDEF
LOG_CHANNEL_ID=C01XYZ
GOOGLE_SHEETS_ID=1abc...
GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/sa.json
DATABASE_PATH=./data/approvals.db
```

**Step 4: 가상환경 생성 및 의존성 설치**

```bash
cd ~/projects/slack-card-approval
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

**Step 5: pytest 빈 실행으로 환경 확인**

```bash
pytest -q
```
Expected: "no tests ran" (실패 아님)

**Step 6: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/__init__.py tests/__init__.py README.md
git commit -m "chore: 프로젝트 스캐폴딩 및 의존성 설정"
```

---

## Task 2: 카테고리 상수

**Files:**
- Create: `src/constants.py`
- Test: `tests/test_constants.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_constants.py
from constants import CATEGORIES

def test_categories_has_26_items():
    assert len(CATEGORIES) == 26

def test_categories_contains_key_items():
    assert "점심식비" in CATEGORIES
    assert "오사용" in CATEGORIES
    assert "기타비용" in CATEGORIES

def test_categories_are_unique():
    assert len(set(CATEGORIES)) == len(CATEGORIES)
```

**Step 2: 테스트 실패 확인**

```bash
pytest tests/test_constants.py -v
```
Expected: FAIL (ModuleNotFoundError: constants)

**Step 3: 상수 구현**

```python
# src/constants.py
CATEGORIES = [
    "팀관리비", "점심식비", "커피 및 음료", "야근식비",
    "교육식사비", "교육간식비", "업무교통비", "자격증 응시료",
    "사무실 간식", "복리후생비", "주차권 구입", "접대비",
    "사무용품비", "회식비", "주말식비", "회의비",
    "교육훈련비", "도서구입비", "유류비", "우편비",
    "택배 발송비", "정기구독료", "서류발급비", "판촉물제작비",
    "기타비용", "오사용",
]
```

**Step 4: 통과 확인**

```bash
pytest tests/test_constants.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/constants.py tests/test_constants.py
git commit -m "feat: 카드 사용 용도 26개 카테고리 상수"
```

---

## Task 3: Config 모듈 (env 로딩 + 검증)

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_config.py
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
```

**Step 2: 실패 확인**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL

**Step 3: 구현**

```python
# src/config.py
import os
from dataclasses import dataclass

class ConfigError(RuntimeError):
    pass

REQUIRED = [
    "SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET",
    "APPROVER_USER_ID", "LOG_CHANNEL_ID",
    "GOOGLE_SHEETS_ID", "GOOGLE_SERVICE_ACCOUNT_JSON",
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
```

**Step 4: 통과 확인**

```bash
pytest tests/test_config.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: 환경변수 로딩 및 시작 시 검증"
```

---

## Task 4: DB 스키마 및 연결 헬퍼

**Files:**
- Create: `src/db.py`, `src/schema.sql`
- Test: `tests/test_db.py`

**Step 1: 스키마 파일 작성**

```sql
-- src/schema.sql
CREATE TABLE IF NOT EXISTS approvals (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  requester_id    TEXT NOT NULL,
  requester_name  TEXT NOT NULL,
  category        TEXT NOT NULL,
  amount          INTEGER NOT NULL,
  used_date       DATE NOT NULL,
  merchant        TEXT NOT NULL,
  status          TEXT NOT NULL
                  CHECK(status IN ('pending','approved','rejected')),
  decided_by      TEXT,
  decided_at      TIMESTAMP,
  approver_msg_ts TEXT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_status ON approvals(status);
CREATE INDEX IF NOT EXISTS idx_requester ON approvals(requester_id);

CREATE TABLE IF NOT EXISTS sheets_sync_queue (
  approval_id     INTEGER PRIMARY KEY REFERENCES approvals(id),
  last_error      TEXT,
  retry_count     INTEGER DEFAULT 0,
  next_retry_at   TIMESTAMP
);
```

**Step 2: 실패하는 테스트 작성**

```python
# tests/test_db.py
import sqlite3
from db import connect, init_schema

def test_init_schema_creates_tables(tmp_path):
    db_path = tmp_path / "t.db"
    conn = connect(str(db_path))
    init_schema(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "approvals" in tables
    assert "sheets_sync_queue" in tables
```

**Step 3: 실패 확인**

```bash
pytest tests/test_db.py -v
```
Expected: FAIL

**Step 4: 구현**

```python
# src/db.py
import sqlite3
from pathlib import Path

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()

def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```

**Step 5: 통과 확인 및 커밋**

```bash
pytest tests/test_db.py -v
git add src/db.py src/schema.sql tests/test_db.py
git commit -m "feat: SQLite 스키마 및 연결 헬퍼"
```

---

## Task 5: ApprovalRepo (CRUD)

**Files:**
- Create: `src/services/__init__.py`, `src/services/approval_repo.py`
- Test: `tests/test_approval_repo.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_approval_repo.py
import pytest
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo, ApprovalNotPending

@pytest.fixture
def repo(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_schema(conn)
    return ApprovalRepo(conn)

def test_create_pending_returns_row(repo):
    row = repo.create_pending(
        requester_id="U1", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="김밥천국",
    )
    assert row["id"] >= 1
    assert row["status"] == "pending"

def test_decide_sets_status_and_decider(repo):
    row = repo.create_pending(
        requester_id="U1", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="x",
    )
    decided = repo.decide(row["id"], "approved", "U2", "1234.5678")
    assert decided["status"] == "approved"
    assert decided["decided_by"] == "U2"
    assert decided["approver_msg_ts"] == "1234.5678"

def test_decide_twice_raises(repo):
    row = repo.create_pending(
        requester_id="U1", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="x",
    )
    repo.decide(row["id"], "approved", "U2", "1.0")
    with pytest.raises(ApprovalNotPending):
        repo.decide(row["id"], "rejected", "U2", "1.0")
```

**Step 2: 실패 확인**

```bash
pytest tests/test_approval_repo.py -v
```

**Step 3: 구현**

```python
# src/services/approval_repo.py
import sqlite3
from datetime import date, datetime

class ApprovalNotPending(RuntimeError):
    pass

class ApprovalRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_pending(self, *, requester_id, requester_name, category,
                       amount, used_date: date, merchant) -> sqlite3.Row:
        cur = self.conn.execute(
            """INSERT INTO approvals
               (requester_id, requester_name, category, amount, used_date,
                merchant, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (requester_id, requester_name, category, amount,
             used_date.isoformat(), merchant),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self, approval_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM approvals WHERE id = ?", (approval_id,)
        ).fetchone()

    def decide(self, approval_id: int, status: str,
               decided_by: str, approver_msg_ts: str) -> sqlite3.Row:
        assert status in ("approved", "rejected")
        cur = self.conn.execute(
            """UPDATE approvals
                  SET status = ?, decided_by = ?, decided_at = ?,
                      approver_msg_ts = ?
                WHERE id = ? AND status = 'pending'""",
            (status, decided_by, datetime.utcnow().isoformat(),
             approver_msg_ts, approval_id),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            raise ApprovalNotPending(f"approval {approval_id} not pending")
        return self.get(approval_id)
```

**Step 4: 통과 확인 및 커밋**

```bash
pytest tests/test_approval_repo.py -v
git add src/services/ tests/test_approval_repo.py
git commit -m "feat: ApprovalRepo (생성/조회/결정 + 중복 방지)"
```

---

## Task 6: Block Kit — 모달 빌더

**Files:**
- Create: `src/views/__init__.py`, `src/views/modal.py`
- Test: `tests/test_modal.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_modal.py
from views.modal import build_approval_modal

def test_modal_has_correct_callback_id():
    view = build_approval_modal(prefill_name="Ozan")
    assert view["callback_id"] == "approval_submit"
    assert view["type"] == "modal"

def test_modal_prefills_requester_name():
    view = build_approval_modal(prefill_name="Ozan")
    blocks = view["blocks"]
    name_block = next(b for b in blocks if b["block_id"] == "requester_name")
    assert name_block["element"]["initial_value"] == "Ozan"

def test_modal_has_all_26_categories():
    view = build_approval_modal(prefill_name="x")
    cat_block = next(b for b in view["blocks"] if b["block_id"] == "category")
    assert len(cat_block["element"]["options"]) == 26
```

**Step 2: 실패 확인**

```bash
pytest tests/test_modal.py -v
```

**Step 3: 구현**

```python
# src/views/modal.py
from constants import CATEGORIES

def build_approval_modal(*, prefill_name: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "approval_submit",
        "title": {"type": "plain_text", "text": "카드 사용 승인 신청"},
        "submit": {"type": "plain_text", "text": "제출"},
        "close": {"type": "plain_text", "text": "취소"},
        "blocks": [
            {
                "type": "input",
                "block_id": "requester_name",
                "label": {"type": "plain_text", "text": "신청자 이름"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "value",
                    "initial_value": prefill_name,
                },
            },
            {
                "type": "input",
                "block_id": "category",
                "label": {"type": "plain_text", "text": "사용 용도"},
                "element": {
                    "type": "static_select",
                    "action_id": "value",
                    "options": [
                        {"text": {"type": "plain_text", "text": c}, "value": c}
                        for c in CATEGORIES
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "amount",
                "label": {"type": "plain_text", "text": "금액 (원)"},
                "element": {
                    "type": "number_input",
                    "action_id": "value",
                    "is_decimal_allowed": False,
                    "min_value": "1",
                },
            },
            {
                "type": "input",
                "block_id": "used_date",
                "label": {"type": "plain_text", "text": "사용 날짜"},
                "element": {"type": "datepicker", "action_id": "value"},
            },
            {
                "type": "input",
                "block_id": "merchant",
                "label": {"type": "plain_text", "text": "가맹점명"},
                "element": {"type": "plain_text_input", "action_id": "value"},
            },
        ],
    }
```

**Step 4: 통과 및 커밋**

```bash
pytest tests/test_modal.py -v
git add src/views/ tests/test_modal.py
git commit -m "feat: 카드 승인 신청 모달 Block Kit"
```

---

## Task 7: Block Kit — 승인자 DM 카드

**Files:**
- Create: `src/views/approval_card.py`
- Test: `tests/test_approval_card.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_approval_card.py
from datetime import date, datetime
from views.approval_card import build_approval_card, build_decided_card

def _sample_row():
    return {
        "id": 42, "requester_name": "Ozan", "category": "점심식비",
        "amount": 12000, "used_date": "2026-05-28",
        "merchant": "김밥천국", "created_at": "2026-05-28T14:32:00",
        "status": "pending",
    }

def test_pending_card_has_buttons():
    blocks = build_approval_card(_sample_row())
    action_block = next(b for b in blocks if b["type"] == "actions")
    actions = action_block["elements"]
    assert {a["action_id"] for a in actions} == {"approve", "reject"}
    assert all(a["value"] == "42" for a in actions)

def test_pending_card_shows_amount_formatted():
    blocks = build_approval_card(_sample_row())
    text = "".join(str(b) for b in blocks)
    assert "12,000원" in text

def test_decided_card_has_no_buttons():
    row = {**_sample_row(), "status": "approved",
           "decided_by": "U2", "decided_at": "2026-05-28T14:33:00"}
    blocks = build_decided_card(row)
    assert not any(b["type"] == "actions" for b in blocks)
    text = "".join(str(b) for b in blocks)
    assert "승인됨" in text or "✅" in text
```

**Step 2: 실패 확인**

```bash
pytest tests/test_approval_card.py -v
```

**Step 3: 구현**

```python
# src/views/approval_card.py
def _fields(row: dict) -> list:
    return [
        {"type": "mrkdwn", "text": f"*신청자*\n{row['requester_name']}"},
        {"type": "mrkdwn", "text": f"*용도*\n{row['category']}"},
        {"type": "mrkdwn", "text": f"*금액*\n{row['amount']:,}원"},
        {"type": "mrkdwn", "text": f"*사용일*\n{row['used_date']}"},
        {"type": "mrkdwn", "text": f"*가맹점*\n{row['merchant']}"},
        {"type": "mrkdwn", "text": f"*신청일시*\n{row['created_at']}"},
    ]

def build_approval_card(row: dict) -> list:
    aid = str(row["id"])
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"💳 카드 사용 승인 요청 (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
        {"type": "actions", "block_id": "decision", "elements": [
            {"type": "button", "action_id": "approve",
             "text": {"type": "plain_text", "text": "✅ 승인"},
             "style": "primary", "value": aid},
            {"type": "button", "action_id": "reject",
             "text": {"type": "plain_text", "text": "❌ 반려"},
             "style": "danger", "value": aid},
        ]},
    ]

def build_decided_card(row: dict) -> list:
    status_label = "✅ 승인됨" if row["status"] == "approved" else "❌ 반려됨"
    return [
        {"type": "header",
         "text": {"type": "plain_text",
                  "text": f"{status_label} (#{row['id']})"}},
        {"type": "section", "fields": _fields(row)},
        {"type": "context", "elements": [
            {"type": "mrkdwn",
             "text": f"처리자: <@{row['decided_by']}> · "
                     f"처리일시: {row['decided_at']}"}
        ]},
    ]
```

**Step 4: 통과 및 커밋**

```bash
pytest tests/test_approval_card.py -v
git add src/views/approval_card.py tests/test_approval_card.py
git commit -m "feat: 승인자 DM 카드 (pending / decided)"
```

---

## Task 8: Bolt 앱 스켈레톤 + /approval 핸들러

**Files:**
- Create: `src/app.py`, `src/handlers/__init__.py`, `src/handlers/command.py`
- Test: `tests/test_command_handler.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_command_handler.py
from unittest.mock import MagicMock
from handlers.command import handle_approval_command

def test_opens_modal_with_prefill_name():
    ack = MagicMock()
    client = MagicMock()
    client.users_info.return_value = {"user": {"profile": {"display_name": "Ozan"}}}
    body = {"trigger_id": "t1", "user_id": "U1"}
    handle_approval_command(ack=ack, body=body, client=client)
    ack.assert_called_once()
    args = client.views_open.call_args.kwargs
    assert args["trigger_id"] == "t1"
    name_block = next(b for b in args["view"]["blocks"]
                      if b["block_id"] == "requester_name")
    assert name_block["element"]["initial_value"] == "Ozan"
```

**Step 2: 실패 확인**

```bash
pytest tests/test_command_handler.py -v
```

**Step 3: 구현**

```python
# src/handlers/command.py
from views.modal import build_approval_modal

def handle_approval_command(ack, body, client):
    ack()
    user_info = client.users_info(user=body["user_id"])
    profile = user_info["user"]["profile"]
    name = profile.get("display_name") or profile.get("real_name") or ""
    client.views_open(
        trigger_id=body["trigger_id"],
        view=build_approval_modal(prefill_name=name),
    )
```

```python
# src/app.py
from slack_bolt import App
from config import load_config
from handlers.command import handle_approval_command

def create_app(cfg=None) -> App:
    cfg = cfg or load_config()
    app = App(token=cfg.bot_token, signing_secret=cfg.signing_secret)
    app.command("/approval")(handle_approval_command)
    return app
```

**Step 4: 통과 및 커밋**

```bash
pytest tests/test_command_handler.py -v
git add src/app.py src/handlers/ tests/test_command_handler.py
git commit -m "feat: Bolt 앱 스켈레톤 및 /approval 슬래시 커맨드"
```

---

## Task 9: view_submission 핸들러 (모달 제출)

**Files:**
- Create: `src/handlers/view_submission.py`
- Modify: `src/app.py` (핸들러 등록)
- Test: `tests/test_view_submission.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_view_submission.py
from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.view_submission import handle_view_submission

def _view_payload():
    return {
        "callback_id": "approval_submit",
        "state": {"values": {
            "requester_name": {"value": {"value": "Ozan"}},
            "category":       {"value": {"selected_option": {"value": "점심식비"}}},
            "amount":         {"value": {"value": "12000"}},
            "used_date":      {"value": {"selected_date": "2026-05-28"}},
            "merchant":       {"value": {"value": "김밥천국"}},
        }},
    }

def test_inserts_pending_and_dms_approver(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    client = MagicMock()
    client.chat_postMessage.return_value = {"ts": "1.0"}
    ack = MagicMock()
    handle_view_submission(
        ack=ack,
        body={"user": {"id": "U1"}, "view": _view_payload()},
        client=client,
        repo=repo,
        approver_user_id="U_APPR",
    )
    ack.assert_called_once_with()
    rows = conn.execute("SELECT * FROM approvals").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    client.chat_postMessage.assert_called_once()
    kwargs = client.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "U_APPR"
```

**Step 2: 실패 확인**

```bash
pytest tests/test_view_submission.py -v
```

**Step 3: 구현**

```python
# src/handlers/view_submission.py
from datetime import date
from views.approval_card import build_approval_card

def _extract(values: dict, block_id: str, key: str):
    return values[block_id]["value"][key]

def handle_view_submission(*, ack, body, client, repo, approver_user_id):
    values = body["view"]["state"]["values"]
    requester_name = _extract(values, "requester_name", "value")
    category = values["category"]["value"]["selected_option"]["value"]
    amount = int(_extract(values, "amount", "value"))
    used_date = date.fromisoformat(
        values["used_date"]["value"]["selected_date"]
    )
    merchant = _extract(values, "merchant", "value")
    ack()  # 모달 닫기
    row = repo.create_pending(
        requester_id=body["user"]["id"],
        requester_name=requester_name,
        category=category, amount=amount,
        used_date=used_date, merchant=merchant,
    )
    client.chat_postMessage(
        channel=approver_user_id,
        blocks=build_approval_card(dict(row)),
        text=f"카드 승인 요청 #{row['id']}",
    )
```

**Step 4: app.py에 등록**

```python
# src/app.py 에 추가
from handlers.view_submission import handle_view_submission
from services.approval_repo import ApprovalRepo
from db import connect, init_schema

def create_app(cfg=None) -> App:
    cfg = cfg or load_config()
    conn = connect(cfg.database_path); init_schema(conn)
    repo = ApprovalRepo(conn)
    app = App(token=cfg.bot_token, signing_secret=cfg.signing_secret)
    app.command("/approval")(handle_approval_command)

    @app.view("approval_submit")
    def _on_submit(ack, body, client):
        handle_view_submission(ack=ack, body=body, client=client,
                               repo=repo, approver_user_id=cfg.approver_user_id)
    return app
```

**Step 5: 통과 및 커밋**

```bash
pytest tests/test_view_submission.py -v
git add src/handlers/view_submission.py src/app.py tests/test_view_submission.py
git commit -m "feat: 모달 제출 처리 — DB 저장 및 승인자 DM"
```

---

## Task 10: button_actions 핸들러 (승인/반려)

**Files:**
- Create: `src/handlers/buttons.py`
- Modify: `src/app.py`
- Test: `tests/test_buttons.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_buttons.py
import pytest
from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from handlers.buttons import handle_decision

@pytest.fixture
def setup(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    row = repo.create_pending(
        requester_id="U_REQ", requester_name="Ozan",
        category="점심식비", amount=12000,
        used_date=date(2026, 5, 28), merchant="김밥천국",
    )
    return conn, repo, row

def test_approve_updates_status_and_msg(setup):
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(),
    )
    updated = repo.get(row["id"])
    assert updated["status"] == "approved"
    client.chat_update.assert_called_once()
    client.chat_postMessage.assert_any_call(
        channel="C_LOG", blocks=client.chat_postMessage.call_args_list[0].kwargs["blocks"],
        text=f"카드 승인 요청 #{row['id']} 처리 결과",
    )

def test_non_approver_rejected(setup):
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock(); respond = MagicMock()
    body = {
        "user": {"id": "U_HACKER"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    handle_decision(
        ack=ack, body=body, client=client, repo=repo,
        approver_user_id="U_APPR", log_channel_id="C_LOG",
        sheets_sync=MagicMock(), respond=respond,
    )
    assert repo.get(row["id"])["status"] == "pending"
    respond.assert_called_once()

def test_double_click_ignored(setup):
    conn, repo, row = setup
    client = MagicMock(); ack = MagicMock(); respond = MagicMock()
    body = {
        "user": {"id": "U_APPR"},
        "actions": [{"action_id": "approve", "value": str(row["id"])}],
        "message": {"ts": "1.0"}, "channel": {"id": "D1"},
    }
    sheets = MagicMock()
    handle_decision(ack=ack, body=body, client=client, repo=repo,
                    approver_user_id="U_APPR", log_channel_id="C_LOG",
                    sheets_sync=sheets, respond=respond)
    handle_decision(ack=ack, body=body, client=client, repo=repo,
                    approver_user_id="U_APPR", log_channel_id="C_LOG",
                    sheets_sync=sheets, respond=respond)
    assert sheets.call_count == 1  # 두 번째는 무시
```

**Step 2: 실패 확인**

```bash
pytest tests/test_buttons.py -v
```

**Step 3: 구현**

```python
# src/handlers/buttons.py
from views.approval_card import build_decided_card
from services.approval_repo import ApprovalNotPending

def handle_decision(*, ack, body, client, repo, approver_user_id,
                    log_channel_id, sheets_sync, respond=None):
    ack()
    user_id = body["user"]["id"]
    if user_id != approver_user_id:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이 요청을 처리할 권한이 없습니다."})
        return

    action = body["actions"][0]
    approval_id = int(action["value"])
    decision = "approved" if action["action_id"] == "approve" else "rejected"
    msg_ts = body["message"]["ts"]

    try:
        row = repo.decide(approval_id, decision, user_id, msg_ts)
    except ApprovalNotPending:
        if respond:
            respond({"response_type": "ephemeral",
                     "text": "이미 처리된 요청입니다."})
        return

    decided_blocks = build_decided_card(dict(row))
    client.chat_update(
        channel=body["channel"]["id"], ts=msg_ts,
        blocks=decided_blocks,
        text=f"카드 승인 요청 #{row['id']} {decision}",
    )
    client.chat_postMessage(
        channel=log_channel_id, blocks=decided_blocks,
        text=f"카드 승인 요청 #{row['id']} 처리 결과",
    )
    client.chat_postMessage(
        channel=row["requester_id"],
        text=(f"카드 승인 요청 #{row['id']}이(가) "
              f"{'승인' if decision == 'approved' else '반려'}되었습니다."),
    )
    sheets_sync(row)
```

**Step 4: app.py에 등록**

```python
# src/app.py 의 create_app() 마지막에 추가
from handlers.buttons import handle_decision

@app.action("approve")
@app.action("reject")
def _on_decision(ack, body, client, respond):
    handle_decision(
        ack=ack, body=body, client=client, repo=repo,
        approver_user_id=cfg.approver_user_id,
        log_channel_id=cfg.log_channel_id,
        sheets_sync=sheets_sync_fn,  # 다음 태스크에서 주입
        respond=respond,
    )
```

(이번 태스크에서 `sheets_sync_fn`는 임시로 `lambda row: None` 사용)

**Step 5: 통과 및 커밋**

```bash
pytest tests/test_buttons.py -v
git add src/handlers/buttons.py src/app.py tests/test_buttons.py
git commit -m "feat: 승인/반려 버튼 처리 + 권한·중복 방지"
```

---

## Task 11: Google Sheets 동기화

**Files:**
- Create: `src/services/sheets_sync.py`
- Test: `tests/test_sheets_sync.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_sheets_sync.py
from unittest.mock import MagicMock
from services.sheets_sync import build_row, SheetsSync

def test_build_row_orders_columns_correctly():
    row = {
        "id": 42, "requester_name": "Ozan", "category": "점심식비",
        "amount": 12000, "used_date": "2026-05-28",
        "merchant": "김밥천국", "status": "approved",
        "decided_by": "U_APPR", "decided_at": "2026-05-28T14:33",
        "created_at": "2026-05-28T14:32",
    }
    assert build_row(row) == [
        42, "Ozan", "점심식비", 12000, "2026-05-28",
        "김밥천국", "approved", "U_APPR",
        "2026-05-28T14:33", "2026-05-28T14:32",
    ]

def test_sync_appends_row_to_worksheet():
    worksheet = MagicMock()
    sync = SheetsSync(worksheet=worksheet)
    sync({"id": 1, "requester_name": "x", "category": "기타비용",
          "amount": 1, "used_date": "2026-05-28", "merchant": "m",
          "status": "approved", "decided_by": "U", "decided_at": "t",
          "created_at": "t"})
    worksheet.append_row.assert_called_once()
```

**Step 2: 실패 확인**

```bash
pytest tests/test_sheets_sync.py -v
```

**Step 3: 구현**

```python
# src/services/sheets_sync.py
import logging
import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)

HEADER = ["id", "신청자", "용도", "금액", "사용날짜", "가맹점",
          "상태", "승인자", "처리일시", "신청일시"]

def build_row(row: dict) -> list:
    return [
        row["id"], row["requester_name"], row["category"],
        row["amount"], row["used_date"], row["merchant"],
        row["status"], row["decided_by"],
        row["decided_at"], row["created_at"],
    ]

def open_worksheet(service_account_json: str, sheet_id: str):
    creds = Credentials.from_service_account_file(
        service_account_json,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.sheet1
    # 헤더 자동 보장
    existing = ws.row_values(1)
    if existing != HEADER:
        ws.update("A1", [HEADER])
    return ws

class SheetsSync:
    def __init__(self, worksheet):
        self.ws = worksheet

    def __call__(self, row: dict) -> None:
        try:
            self.ws.append_row(build_row(row), value_input_option="USER_ENTERED")
        except Exception as e:
            log.error("Sheets sync 실패 id=%s: %s", row.get("id"), e)
            raise
```

**Step 4: app.py에 주입**

```python
# src/app.py
from services.sheets_sync import SheetsSync, open_worksheet

# create_app() 안:
ws = open_worksheet(cfg.service_account_json, cfg.sheets_id)
sheets_sync_fn = SheetsSync(ws)
```

**Step 5: 통과 및 커밋**

```bash
pytest tests/test_sheets_sync.py -v
git add src/services/sheets_sync.py src/app.py tests/test_sheets_sync.py
git commit -m "feat: Google Sheets 결정 시점 동기화"
```

---

## Task 12: Sheets 실패 시 큐 적재 + 재시도 워커

**Files:**
- Modify: `src/services/sheets_sync.py` (실패 시 큐 적재)
- Create: `src/services/sheets_retry.py`
- Test: `tests/test_sheets_retry.py`

**Step 1: 실패하는 테스트 작성**

```python
# tests/test_sheets_retry.py
from unittest.mock import MagicMock
from datetime import date
from db import connect, init_schema
from services.approval_repo import ApprovalRepo
from services.sheets_retry import enqueue, drain_once

def test_enqueue_then_drain(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    repo = ApprovalRepo(conn)
    row = repo.create_pending(
        requester_id="U", requester_name="x", category="기타비용",
        amount=1, used_date=date(2026, 5, 28), merchant="m",
    )
    repo.decide(row["id"], "approved", "U2", "1.0")
    enqueue(conn, row["id"], "boom")
    pending = conn.execute(
        "SELECT * FROM sheets_sync_queue").fetchall()
    assert len(pending) == 1

    sync = MagicMock()
    drain_once(conn, repo, sync)
    sync.assert_called_once()
    after = conn.execute("SELECT * FROM sheets_sync_queue").fetchall()
    assert after == []
```

**Step 2: 실패 확인**

```bash
pytest tests/test_sheets_retry.py -v
```

**Step 3: 구현**

```python
# src/services/sheets_retry.py
import sqlite3

def enqueue(conn: sqlite3.Connection, approval_id: int, error: str) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO sheets_sync_queue
           (approval_id, last_error, retry_count, next_retry_at)
           VALUES (?, ?,
                   COALESCE((SELECT retry_count FROM sheets_sync_queue
                             WHERE approval_id = ?), 0) + 1,
                   datetime('now', '+5 minutes'))""",
        (approval_id, error, approval_id),
    )
    conn.commit()

def drain_once(conn, repo, sync) -> int:
    ids = [r[0] for r in conn.execute(
        """SELECT approval_id FROM sheets_sync_queue
           WHERE next_retry_at <= datetime('now')"""
    ).fetchall()]
    n = 0
    for aid in ids:
        row = repo.get(aid)
        try:
            sync(dict(row))
            conn.execute("DELETE FROM sheets_sync_queue WHERE approval_id = ?",
                         (aid,))
            conn.commit()
            n += 1
        except Exception:
            pass  # next_retry_at 그대로, 다음 사이클에서 재시도
    return n
```

**Step 4: SheetsSync 호출부에서 실패 시 큐 적재**

`src/handlers/buttons.py`의 `sheets_sync(row)` 호출을 try/except로 감싸고 실패 시 `enqueue(conn, row["id"], str(e))` 호출하도록 수정. `conn`을 핸들러에 주입.

**Step 5: 백그라운드 워커 스레드**

`src/app.py`에서 `threading.Thread`로 5분마다 `drain_once` 호출 (`time.sleep(300)`). 데몬 스레드.

**Step 6: 통과 및 커밋**

```bash
pytest tests/test_sheets_retry.py -v
git add src/services/sheets_retry.py src/handlers/buttons.py src/app.py tests/test_sheets_retry.py
git commit -m "feat: Sheets 동기화 실패 시 큐 적재 및 5분 재시도 워커"
```

---

## Task 13: 앱 엔트리포인트 + 시작 검증

**Files:**
- Create: `src/main.py`

**Step 1: 구현**

```python
# src/main.py
import os
import logging
from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode import SocketModeHandler

logging.basicConfig(level=logging.INFO)
load_dotenv()

from app import create_app
from config import load_config

def main():
    cfg = load_config()
    app = create_app(cfg)
    if cfg.app_token:
        SocketModeHandler(app, cfg.app_token).start()
    else:
        # HTTP 모드: gunicorn 같은 wsgi 서버와 연결 가능하지만
        # 단순 실행은 내장 dev 서버 사용
        app.start(port=int(os.environ.get("PORT", 3000)))

if __name__ == "__main__":
    main()
```

**Step 2: 실행 시 환경변수 누락 검증 확인**

```bash
# .env 파일 없이 실행
python src/main.py
```
Expected: `ConfigError: 필수 환경변수 누락: SLACK_BOT_TOKEN, ...`

**Step 3: Commit**

```bash
git add src/main.py
git commit -m "feat: 앱 엔트리포인트 (Socket Mode / HTTP 자동 전환)"
```

---

## Task 14: Dockerfile + docker-compose

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`

**Step 1: Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY src/ ./src/
ENV PYTHONPATH=/app/src

VOLUME ["/data", "/secrets"]
CMD ["python", "src/main.py"]
```

**Step 2: docker-compose.yml**

```yaml
services:
  app:
    build: .
    env_file: .env
    volumes:
      - ./data:/data
      - ./secrets:/secrets
    ports:
      - "3000:3000"   # HTTP 모드 사용 시
    restart: unless-stopped
```

**Step 3: 빌드 확인**

```bash
docker compose build
```
Expected: 성공

**Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "chore: Docker 패키징"
```

---

## Task 15: README + 운영 가이드

**Files:**
- Modify: `README.md`

**Step 1: README 작성**

다음 섹션 포함:
- 무엇을 하는 앱인가 (한 단락)
- Slack 앱 생성 절차: bot scopes (`commands`, `chat:write`, `chat:write.public`, `users:read`), 슬래시 커맨드 `/approval` 등록, interactivity 활성화, Socket Mode 또는 Request URL 설정
- Google Cloud 서비스 계정 생성 + Sheets 공유 절차
- `.env` 작성 안내
- `docker compose up` 실행
- 개발 모드 (`ngrok http 3000`) 안내
- 테스트 실행: `pytest`

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README 및 운영 가이드"
```

---

## Task 16: 수동 스모크 테스트

**Step 1**: `.env` 파일에 실제 토큰 채우고 `docker compose up`

**Step 2**: Slack에서 `/approval` 입력 → 모달 열림 확인 → 폼 작성 후 제출

**Step 3**: 승인자 계정 DM에 카드 도착 확인 → `[승인]` 클릭

**Step 4**:
- DM 메시지가 "승인됨"으로 업데이트되는지
- 신청자에게 결과 DM이 오는지
- `#카드승인-로그` 채널에 카드가 게시되는지
- Google Sheet에 새 행이 추가되는지

**Step 5**: 두 번째 신청 후 `[반려]` 클릭 → 동일하게 흐름 검증

**Step 6**: 권한 외 사용자가 승인 버튼 클릭 시 ephemeral 에러 확인 (테스트 어렵다면 코드 리뷰로 대체)

---

## 완료 기준

- 모든 단위 테스트 통과 (`pytest`)
- 수동 스모크 테스트 6단계 모두 OK
- README만 보고 새 사람이 30분 안에 자기 워크스페이스에 배포 가능

## 참고 스킬

- @superpowers:test-driven-development — 각 태스크의 TDD 사이클
- @superpowers:verification-before-completion — 태스크 완료 전 검증
- @superpowers:executing-plans — 이 계획 실행
