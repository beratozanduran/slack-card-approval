import logging
import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)

HEADER = ["id", "신청자", "용도", "금액", "사용날짜", "가맹점",
          "상태", "승인자", "반려사유", "처리일시", "신청일시"]

# 상태 코드를 사람이 읽는 한국어로 변환
STATUS_LABEL = {"pending": "대기중", "approved": "승인", "rejected": "반려"}


def _to_str(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def build_row(row: dict) -> list:
    # 승인자는 ID가 아닌 표시 이름을 기록한다(없으면 ID로 폴백).
    approver = row.get("decided_by_name") or row.get("decided_by")
    return [
        row["id"], row["requester_name"], row["category"],
        row["amount"], _to_str(row["used_date"]), row["merchant"],
        STATUS_LABEL.get(row["status"], row["status"]), approver,
        row.get("reject_reason") or "",
        _to_str(row["decided_at"]), _to_str(row["created_at"]),
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
