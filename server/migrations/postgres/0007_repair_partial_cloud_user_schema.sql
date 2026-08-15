ALTER TABLE users
ADD COLUMN IF NOT EXISTS email TEXT;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS email_verified INTEGER DEFAULT 0;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS chat_enabled INTEGER DEFAULT 1;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_auth_enabled INTEGER DEFAULT 1;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS onboarding_completed INTEGER DEFAULT 1;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS account_status TEXT DEFAULT 'active';

ALTER TABLE users
ADD COLUMN IF NOT EXISTS registered_at TEXT;

UPDATE users
SET email_verified = 0
WHERE email_verified IS NULL;

UPDATE users
SET chat_enabled = 1
WHERE chat_enabled IS NULL;

UPDATE users
SET password_auth_enabled = 1
WHERE password_auth_enabled IS NULL;

UPDATE users
SET onboarding_completed = 1
WHERE onboarding_completed IS NULL;

UPDATE users
SET account_status = 'active'
WHERE account_status IS NULL OR account_status = '';

UPDATE users
SET registered_at = CURRENT_TIMESTAMP
WHERE registered_at IS NULL OR registered_at = '';

INSERT INTO schema_migrations(version)
VALUES ('0007_repair_partial_cloud_user_schema')
ON CONFLICT (version) DO NOTHING;
