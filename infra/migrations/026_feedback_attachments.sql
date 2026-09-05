CREATE TABLE IF NOT EXISTS feedback_attachments (
    id UUID PRIMARY KEY,
    feedback_id UUID NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL,
    data BYTEA NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_feedback_attachments_feedback
    ON feedback_attachments (feedback_id, created_at);
