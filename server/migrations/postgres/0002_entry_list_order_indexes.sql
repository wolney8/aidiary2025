CREATE INDEX IF NOT EXISTS idx_daily_entries_user_list_order
ON dailydiary_entries(
    user_id,
    entry_date DESC,
    (COALESCE(entry_time, '19:00')) DESC,
    entry_number DESC,
    id DESC
);

CREATE INDEX IF NOT EXISTS idx_dream_entries_user_list_order
ON dreamdiary_entries(
    user_id,
    entry_date DESC,
    (COALESCE(entry_time, '08:00')) DESC,
    entry_number DESC,
    id DESC
);
