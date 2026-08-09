ALTER TABLE subscriptions
ADD COLUMN IF NOT EXISTS billing_period TEXT;

ALTER TABLE subscriptions
ADD COLUMN IF NOT EXISTS provider_price_id TEXT;
