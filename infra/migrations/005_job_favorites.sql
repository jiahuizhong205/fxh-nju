CREATE TABLE IF NOT EXISTS job_favorites (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id VARCHAR(50) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_job_favorites_user_job UNIQUE (user_id, job_id)
);

CREATE INDEX IF NOT EXISTS ix_job_favorites_user_id ON job_favorites (user_id);
