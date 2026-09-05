ALTER TABLE sync_records
    ADD COLUMN IF NOT EXISTS provider_status VARCHAR(20) NOT NULL DEFAULT 'disabled';

ALTER TABLE sync_records
    ADD COLUMN IF NOT EXISTS provider_error TEXT NOT NULL DEFAULT '';

ALTER TABLE sync_records
    ADD COLUMN IF NOT EXISTS provider_synced_at TIMESTAMP NULL;
