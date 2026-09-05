ALTER TABLE verification_challenges
    ADD COLUMN IF NOT EXISTS provider_message_id VARCHAR(200) NOT NULL DEFAULT '';
