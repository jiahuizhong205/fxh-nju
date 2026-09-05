CREATE TABLE IF NOT EXISTS sync_records (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error TEXT NOT NULL DEFAULT '',
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sync_records_user_scope UNIQUE (user_id, scope),
    CONSTRAINT ck_sync_records_status CHECK (status IN ('pending', 'synced', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_sync_records_user_updated
    ON sync_records (user_id, updated_at DESC);
