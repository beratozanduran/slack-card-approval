import sqlite3
import logging

log = logging.getLogger(__name__)


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
            conn.execute(
                "DELETE FROM sheets_sync_queue WHERE approval_id = ?",
                (aid,),
            )
            conn.commit()
            n += 1
        except Exception as e:
            log.error("Sheets retry 여전히 실패 id=%s: %s", aid, e)
    return n
