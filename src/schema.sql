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
