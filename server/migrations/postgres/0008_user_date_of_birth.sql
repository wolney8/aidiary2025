ALTER TABLE users
ADD COLUMN IF NOT EXISTS date_of_birth TEXT;

INSERT INTO schema_migrations(version)
VALUES ('0008_user_date_of_birth')
ON CONFLICT (version) DO NOTHING;
