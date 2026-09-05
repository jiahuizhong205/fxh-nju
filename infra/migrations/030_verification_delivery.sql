ALTER TABLE verification_challenges
    ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(20) NOT NULL DEFAULT 'queued';
ALTER TABLE verification_challenges
    ADD COLUMN IF NOT EXISTS delivery_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE verification_challenges
    ADD COLUMN IF NOT EXISTS delivery_error TEXT NOT NULL DEFAULT '';
ALTER TABLE verification_challenges
    ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP NULL;
