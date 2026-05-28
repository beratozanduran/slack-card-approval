import logging
import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)

HEADER = ["id", "신청자", "용도", "금액", "사용날짜", "가맹점",
          "상태", "승인자", "처리일시", "신청일시"]


def _to_str(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def build_row(row: dict) -> list:
    return [
        row["id"], row["requester_name"], row["category"],
        row["amount"], _to_str(row["used_date"]), row["merchant"],
        row["status"], row["decided_by"],
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
