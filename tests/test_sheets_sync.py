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
