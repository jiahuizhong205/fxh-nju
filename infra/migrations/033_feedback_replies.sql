CREATE TABLE IF NOT EXISTS feedback_replies (
    id UUID PRIMARY KEY,
    feedback_id UUID NOT NULL REFERENCES feedback(id) ON DELETE CASCADE,
    admin_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_feedback_replies_feedback_id
    ON feedback_replies (feedback_id, created_at);
