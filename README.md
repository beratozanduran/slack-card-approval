# Slack 법인카드 승인 앱

팀 내부에서 법인카드 사용 내역을 Slack 안에서 신청·승인·기록한다. 요청자가 `/approval` 슬래시 커맨드로 모달을 띄워 사용 내역을 제출하면, 지정된 승인자가 DM 카드에서 한 번의 클릭으로 승인/반려를 결정한다. 모든 결과는 고정 채널과 Google Sheets에 자동 적재된다.

## 사용 흐름

```
신청자: /approval → 모달 작성 → 제출
       ↓
승인자(DM): 카드 수신 → [✅ 승인] / [❌ 반려]
       ↓
- 승인자 DM 메시지가 결과로 업데이트
- 신청자에게 결과 DM 알림
- #카드승인-로그 채널에 결과 카드 게시
- Google Sheets에 한 행 자동 추가
```

## 1. Slack 앱 생성

1. https://api.slack.com/apps 에서 **Create New App** → **From scratch**
2. 앱 이름·워크스페이스 선택
3. **OAuth & Permissions** → Bot Token Scopes 추가:
   - `commands` — 슬래시 커맨드용
   - `chat:write` — 메시지 전송
   - `chat:write.public` — 봇이 초대되지 않은 공개 채널에도 쓸 수 있게(로그 채널)
   - `users:read` — 신청자 프로필 조회(이름 자동 채움)
4. **Slash Commands** → `/approval` 등록
   - Socket Mode 사용 시 Request URL 비워두기
   - HTTP 모드 사용 시 `https://<your-domain>/slack/events`
5. **Interactivity & Shortcuts** → 활성화
   - Socket Mode면 Request URL 비워두기
   - HTTP면 `/slack/events` 동일 경로
6. **Socket Mode** (권장 — Request URL 없이 동작)
   - 활성화 후 **App-Level Token** 생성 (`connections:write` scope)
   - 발급된 `xapp-...` 토큰을 `.env`의 `SLACK_APP_TOKEN`에 저장
7. **Install App** → 워크스페이스 설치
8. 발급된 토큰 두 개 확보:
   - **Bot User OAuth Token** (`xoxb-...`) → `.env`의 `SLACK_BOT_TOKEN`
   - **Signing Secret** (Basic Information 페이지) → `.env`의 `SLACK_SIGNING_SECRET`

## 2. Google Sheets 준비

1. https://console.cloud.google.com/ 에서 프로젝트 생성
2. **APIs & Services → Library**에서 **Google Sheets API** 활성화
3. **APIs & Services → Credentials → Create Credentials → Service Account**
4. 서비스 계정 생성 후 **Keys → Add Key → JSON** 으로 키 파일 다운로드 → `./secrets/sa.json`으로 저장
5. 사용할 Google Sheet 생성 후, 서비스 계정 이메일(예: `xxx@<project>.iam.gserviceaccount.com`)을 **편집자**로 공유
6. 시트 URL에서 ID 추출: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit` → `.env`의 `GOOGLE_SHEETS_ID`

## 3. 환경변수

`.env.example`을 `.env`로 복사하고 값을 채운다:

```
SLACK_BOT_TOKEN=xoxb-...              # Slack Bot 토큰
SLACK_SIGNING_SECRET=...              # Slack Signing Secret
SLACK_APP_TOKEN=xapp-...              # Socket Mode 사용 시. 없으면 HTTP 모드
APPROVER_USER_ID=U01ABCDEF            # 승인자 Slack User ID
LOG_CHANNEL_ID=C01XYZ                 # 결과 로그 채널 ID
GOOGLE_SHEETS_ID=1abc...              # Google Sheet ID
GOOGLE_SERVICE_ACCOUNT_JSON=./secrets/sa.json
DATABASE_PATH=./data/approvals.db
```

Slack User ID / Channel ID는 Slack에서 우클릭 → "Copy member ID" / "Copy link"로 확인.

## 4. 실행

### Docker (권장)

```bash
docker compose up --build
```

`./data`와 `./secrets`이 컨테이너에 마운트된다. SQLite DB와 서비스 계정 JSON이 이 경로에 위치해야 함.

### 로컬 개발

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python src/main.py
```

#### Socket Mode가 아닌 HTTP 모드를 쓸 때

`SLACK_APP_TOKEN`을 비워두면 HTTP 모드. 포트 3000 노출. 외부에서 도달 가능해야 하므로 개발 시 `ngrok`:

```bash
ngrok http 3000
# 출력된 https URL을 Slack 앱 설정의 Request URL에 등록
```

## 5. 테스트

```bash
.venv/bin/pytest -v
```

23개의 단위 테스트 실행. Slack/Sheets API는 모두 mock 처리됨.

## 6. 디렉토리 구조

```
src/
  app.py              Bolt 앱 생성 (create_app)
  main.py             엔트리포인트
  config.py           환경변수 로딩 + 검증
  constants.py        26개 카테고리
  db.py               SQLite 연결 헬퍼
  schema.sql          DB 스키마
  handlers/
    command.py        /approval slash command
    view_submission.py 모달 제출
    buttons.py        승인/반려 버튼
  services/
    approval_repo.py  Repository (CRUD + status 전이)
    sheets_sync.py    Google Sheets 동기화
    sheets_retry.py   실패 큐 + drain
  views/
    modal.py          신청 모달 Block Kit
    approval_card.py  승인자 DM 카드 / 결과 카드
tests/                pytest 단위 테스트
docs/plans/           설계 문서 + 구현 계획
Dockerfile
docker-compose.yml
```

## 7. 트러블슈팅

- **`ConfigError: 필수 환경변수 누락`** — `.env` 또는 컨테이너 env에 명시되지 않은 키가 있음. 에러 메시지에 누락된 키가 나옴.
- **`/approval`을 입력해도 모달이 안 뜬다** — Bot Token 권한(`commands`, `users:read`) 확인, Slash Command가 등록됐는지 확인.
- **승인자 DM이 안 온다** — `APPROVER_USER_ID`가 올바른 Slack User ID(U로 시작)인지, 봇이 해당 사용자에게 DM 보낼 권한(`chat:write`)이 있는지 확인.
- **`#카드승인-로그`에 메시지가 안 보인다** — 봇을 채널에 초대(`/invite @<botname>`)하거나 `chat:write.public` 권한 부여.
- **Google Sheets 행이 안 추가됨** — 서비스 계정 이메일이 시트의 편집자로 공유됐는지, `GOOGLE_SHEETS_ID`가 맞는지 확인. 실패 시 자동으로 큐에 적재되고 5분마다 재시도.

## 8. 향후 확장

`docs/plans/2026-05-28-slack-card-approval-design.md`의 "향후 확장 후보" 섹션 참조.
