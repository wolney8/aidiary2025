-- Destructive rollback for the CBT worksheet baseline.
-- Export or back up worksheet data before applying this script.
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS cbt_thought_record_data;
DROP TABLE IF EXISTS cbt_worksheets;
