ALTER TABLE feedback_attachments
    ADD COLUMN IF NOT EXISTS storage_backend VARCHAR(30) NOT NULL DEFAULT 'database';

ALTER TABLE feedback_attachments
    ADD COLUMN IF NOT EXISTS storage_key TEXT NOT NULL DEFAULT '';

ALTER TABLE feedback_attachments
    ADD COLUMN IF NOT EXISTS scan_status VARCHAR(20) NOT NULL DEFAULT 'clean';
