# Slack 법인카드 승인 앱 — 설계 문서

- 작성일: 2026-05-28
- 작성자: Ozan (오잔)
- 상태: 승인됨 (브레인스토밍 단계 완료)

## 1. 배경 및 목적

Nextcloud 팀 내부에서 법인카드 사용 내역을 정산할 때, 슬랙 안에서 신청·승인·기록을 한 번에 끝내기 위한 앱. 메일·구두 보고 없이 슬랙에서 모달을 작성하고, 승인자가 DM 카드로 받아 한 번의 버튼 클릭으로 결정을 내린다. 모든 결과는 채널 로그와 Google Sheets에 자동 적재된다.

## 2. 범위 / 비범위

**범위 (MVP)**
- 단일 승인자 워크플로우 (환경변수로 지정한 한 명)
- 슬래시 커맨드 `/approval` 트리거
- 26개 사전 정의된 카드 사용 용도 카테고리
- SQLite 영구 저장
- `#카드승인-로그` 채널에 결과 게시
- Google Sheets 자동 동기화 (결정 시점에만)

**비범위 (YAGNI)**
- 다수 승인자, 결재 라인
- 영수증 이미지 업로드
- 외부 시스템 웹훅 트리거
- 통계 대시보드
- 카테고리별 한도/규칙 검증

## 3. 사용자 흐름

```
요청자                       Bolt 앱                    승인자                  채널 / Sheets
  │                             │                          │                         │
  │ /approval 입력              │                          │                         │
  ├────────────────────────────►│                          │                         │
  │                             │ 모달 응답                │                         │
  │◄────────────────────────────┤                          │                         │
  │                             │                          │                         │
  │ 모달 제출                   │                          │                         │
  ├────────────────────────────►│                          │                         │
  │                             │ DB insert (pending)      │                         │
  │                             │ "접수됨" ephemeral 응답  │                         │
  │◄────────────────────────────┤                          │                         │
  │                             │ DM 승인 카드 push        │                         │
  │                             ├─────────────────────────►│                         │
  │                             │                          │ 승인/반려 버튼 클릭    │
  │                             │◄─────────────────────────┤                         │
  │                             │ DB update + 메시지 갱신  │                         │
  │                             ├─────────────────────────►│                         │
  │                             │ 로그 채널 게시           │                         │
  │                             ├────────────────────────────────────────────────────►│
  │                             │ Sheets 행 추가           │                         │
  │                             ├────────────────────────────────────────────────────►│
  │ 결과 DM                     │                          │                         │
  │◄────────────────────────────┤                          │                         │
```

## 4. 아키텍처

```
   Slack 워크스페이스
   ┌──────────────────────────┐
   │ /approval slash command  │
   │ block_actions (button)   │
   │ view_submission (modal)  │
   └─────────────┬────────────┘
                 │ HTTPS (Slack 서명 검증)
                 ▼
   ┌────────────────────────────────────┐
   │ Slack Bolt 앱 (Python)              │
   │                                    │
   │  handlers/                         │
   │    - command_approval.py          │
   │    - view_submission.py           │
   │    - button_actions.py            │
   │                                    │
   │  services/                         │
   │    - approval_repo.py  (SQLite)   │
   │    - sheets_sync.py    (gspread)  │
   │    - slack_notify.py   (Bolt API) │
   │                                    │
   │  views/                            │
   │    - modal.py        (Block Kit)  │
   │    - approval_card.py             │
   │    - log_card.py                  │
   │                                    │
   │  app.py, config.py                │
   └────────────┬────────────┬──────────┘
                │            │
                ▼            ▼
        SQLite (volume)   Google Sheets API
```

**런타임 패키지**: `slack-bolt`, `gspread`, `google-auth`, `python-dotenv`, `pytest` (dev)

## 5. 데이터 모델 (SQLite)

```sql
CREATE TABLE approvals (
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

CREATE INDEX idx_status ON approvals(status);
CREATE INDEX idx_requester ON approvals(requester_id);

CREATE TABLE sheets_sync_queue (
  approval_id     INTEGER PRIMARY KEY REFERENCES approvals(id),
  last_error      TEXT,
  retry_count     INTEGER DEFAULT 0,
  next_retry_at   TIMESTAMP
);
```

**컬럼 의도**:
- `approver_msg_ts` — 승인자 DM 메시지를 결정 후 in-place 업데이트
- `sheets_sync_queue` — Sheets API 실패 시 재시도 대상 적재

## 6. 카테고리 (사용 용도)

```
팀관리비, 점심식비, 커피 및 음료, 야근식비, 교육식사비, 교육간식비,
업무교통비, 자격증 응시료, 사무실 간식, 복리후생비, 주차권 구입,
접대비, 사무용품비, 회식비, 주말식비, 회의비, 교육훈련비,
도서구입비, 유류비, 우편비, 택배 발송비, 정기구독료,
서류발급비, 판촉물제작비, 기타비용, 오사용
```

상수 파일(`constants.py`)에 리스트로 보관, 모달 dropdown options 생성에 사용.

## 7. Slack UI (Block Kit)

### 7.1 모달 (`/approval` 진입)

```
┌─ 카드 사용 승인 신청 ──────────┐
│ 신청자 이름   [Ozan _______] │  plain_text_input (Slack 표시명 prefill)
│ 사용 용도     [▼ ────────]   │ static_select (26 options)
│ 금액 (원)     [_____________] │ plain_text_input (number)
│ 사용 날짜     [📅 2026-05-28] │ datepicker
│ 가맹점명      [_____________] │ plain_text_input
│                              │
│              [취소]  [제출]   │
└─────────────────────────────┘
```

### 7.2 승인자 DM 카드

```
💳 카드 사용 승인 요청 (#42)
신청자:    Ozan
용도:      점심식비
금액:      12,000원
사용일:    2026-05-28
가맹점:    김밥천국 강남점
신청일시:  2026-05-28 14:32

[✅ 승인]  [❌ 반려]
```

버튼 클릭 후 메시지가 `✅ 승인됨 (by @팀장, 14:33)` 또는 `❌ 반려됨` 헤더로 in-place 업데이트.

### 7.3 로그 채널 (`#카드승인-로그`) 게시

7.2와 동일 포맷에 결과 헤더만 적용된 카드.

## 8. Google Sheets 연동

- 인증: 서비스 계정 JSON (`GOOGLE_SERVICE_ACCOUNT_JSON` env)
- 라이브러리: `gspread`
- 시트 ID: `GOOGLE_SHEETS_ID` env
- 동기화 시점: 승인/반려 결정 직후 (pending은 동기화 안 함)
- 컬럼 순서: `id | 신청자 | 용도 | 금액 | 사용날짜 | 가맹점 | 상태 | 승인자 | 처리일시 | 신청일시`

실패 시 `sheets_sync_queue`에 적재 후 백그라운드 워커(`scheduler` 모듈, 5분 간격)가 재시도.

## 9. 에러 처리

| 상황 | 대응 |
|---|---|
| 비-승인자가 버튼 클릭 (이론상 DM이므로 발생 어려움) | `user.id != APPROVER_USER_ID` 시 ephemeral 에러 |
| 이미 처리된 요청 재클릭 | DB `status` 체크, pending 아니면 ephemeral "이미 처리됨" |
| 모달 입력 오류 (금액 음수/비숫자, 미래 날짜 등) | `view_submission` 에서 `response_action=errors` 반환 |
| Slack API 실패 | 로그 + ephemeral 재시도 안내 |
| Sheets API 실패 | Slack 흐름은 성공 처리. 큐에 적재 후 백그라운드 재시도 |
| 봇 토큰 / 채널 ID 누락 | startup 시 환경변수 검증, 빠른 실패 |

## 10. 배포

**환경변수**
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
APPROVER_USER_ID=U01ABCDEF
LOG_CHANNEL_ID=C01XYZ
GOOGLE_SHEETS_ID=1abc...
GOOGLE_SERVICE_ACCOUNT_JSON=/secrets/sa.json
DATABASE_PATH=/data/approvals.db
```

**패키징**
- Docker 단일 컨테이너
- SQLite는 `/data` 볼륨 마운트
- 서비스 계정 JSON은 `/secrets` 볼륨 마운트

**개발 환경**: `ngrok http 3000`으로 Slack에 요청 URL 노출
**프로덕션 후보**: 사내 서버 systemd 또는 Fly.io 무료 티어

## 11. 테스트 전략

- **단위 테스트**: 핸들러(모달 payload 파싱, DB write, status 전이), Block Kit JSON 빌더 (snapshot)
- **통합 테스트**: Bolt의 `App.test_client`로 핸들러-DB 경로 검증
- **외부 의존성**: Slack/Sheets API는 `pytest-mock` 으로 모킹
- **수동 스모크**: 개발 ngrok 환경에서 end-to-end 한 번 실행

## 12. 향후 확장 후보 (메모만)

- 다수 승인자 / 결재 라인
- 카테고리별 한도 검증
- 영수증 이미지 업로드 (Slack file_id → Sheets 링크)
- 월별 자동 리포트 (스케줄 작업)
