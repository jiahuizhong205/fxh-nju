CREATE TABLE IF NOT EXISTS recommendation_reports (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    profile_version INTEGER NOT NULL DEFAULT 0,
    profile_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_recommendation_reports_user_id
    ON recommendation_reports (user_id, created_at DESC);
