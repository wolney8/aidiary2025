ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS user_message TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS ai_response TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS daily_people_names TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS daily_places TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS tags TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS entry_time TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS mood TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS ai_style TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS image_url TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS image_storage_key TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS image_source TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS image_prompt TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS recycled_image_prompt TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS image_position_x DOUBLE PRECISION DEFAULT 50;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS image_position_y DOUBLE PRECISION DEFAULT 50;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS analysis_attachment_refs TEXT;

ALTER TABLE dailydiary_entries
ADD COLUMN IF NOT EXISTS import_id BIGINT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS title TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS plot TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS summary TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS interpretation TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS dream_people_names TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS dream_places TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS tags TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS entry_time TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS mood TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS ai_style TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS image_url TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS image_storage_key TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS image_source TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS image_prompt TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS recycled_image_prompt TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS image_position_x DOUBLE PRECISION DEFAULT 50;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS image_position_y DOUBLE PRECISION DEFAULT 50;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS analysis_attachment_refs TEXT;

ALTER TABLE dreamdiary_entries
ADD COLUMN IF NOT EXISTS import_id BIGINT;

INSERT INTO schema_migrations(version)
VALUES ('0009_repair_entry_search_schema')
ON CONFLICT (version) DO NOTHING;
