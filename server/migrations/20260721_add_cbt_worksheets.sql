PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cbt_worksheets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    worksheet_type    TEXT NOT NULL DEFAULT 'thought_record',
    title             TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'draft'
                      CHECK(status IN ('draft', 'completed')),
    current_step      INTEGER NOT NULL DEFAULT 1 CHECK(current_step BETWEEN 1 AND 7),
    record_date       TEXT NOT NULL DEFAULT CURRENT_DATE,
    linked_entry_type TEXT CHECK(linked_entry_type IN ('daily', 'dream')),
    linked_entry_id   INTEGER,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at      TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(
        (linked_entry_type IS NULL AND linked_entry_id IS NULL) OR
        (linked_entry_type IS NOT NULL AND linked_entry_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS cbt_thought_record_data (
    worksheet_id         INTEGER PRIMARY KEY,
    situation            TEXT NOT NULL DEFAULT '',
    feelings_before_json TEXT NOT NULL DEFAULT '[]',
    unhelpful_thoughts   TEXT NOT NULL DEFAULT '',
    evidence_for         TEXT NOT NULL DEFAULT '',
    evidence_against     TEXT NOT NULL DEFAULT '',
    balanced_thought     TEXT NOT NULL DEFAULT '',
    feelings_after_json  TEXT NOT NULL DEFAULT '[]',
    next_step            TEXT NOT NULL DEFAULT '',
    ai_response          TEXT NOT NULL DEFAULT '',
    ai_responded_at      TEXT,
    ai_response_outdated INTEGER NOT NULL DEFAULT 0
                         CHECK(ai_response_outdated IN (0, 1)),
    FOREIGN KEY (worksheet_id) REFERENCES cbt_worksheets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_user_status
ON cbt_worksheets(user_id, status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_linked_entry
ON cbt_worksheets(user_id, linked_entry_type, linked_entry_id)
WHERE linked_entry_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_cbt_worksheets_user_date
ON cbt_worksheets(user_id, record_date, id);
