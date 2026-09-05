CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    body TEXT NOT NULL,
    channel VARCHAR(30) NOT NULL DEFAULT 'in_app',
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    scheduled_at TIMESTAMP NULL,
    sent_at TIMESTAMP NULL,
    read_at TIMESTAMP NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_notifications_status CHECK (status IN ('queued', 'sent', 'read', 'failed'))
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_created
    ON notifications (user_id, created_at DESC);
