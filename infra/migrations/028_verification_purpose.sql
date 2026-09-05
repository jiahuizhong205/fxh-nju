ALTER TABLE verification_challenges
    ADD COLUMN IF NOT EXISTS purpose VARCHAR(30) NOT NULL DEFAULT 'contact_verification';
