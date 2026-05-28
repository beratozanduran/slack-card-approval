import sqlite3
from datetime import date, datetime, timezone


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
            (status, decided_by,
             datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" "),
             approver_msg_ts, approval_id),
        )
        self.conn.commit()
        if cur.rowcount == 0:
            raise ApprovalNotPending(f"approval {approval_id} not pending")
        return self.get(approval_id)
