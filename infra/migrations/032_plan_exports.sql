CREATE TABLE IF NOT EXISTS plan_exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES learning_plans(id) ON DELETE CASCADE,
    format VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    content_sha256 VARCHAR(64) NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);
CREATE INDEX IF NOT EXISTS ix_plan_exports_user_created
    ON plan_exports (user_id, created_at DESC);
