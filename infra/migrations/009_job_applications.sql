CREATE TABLE IF NOT EXISTS job_applications (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id VARCHAR(50) NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'interested',
    channel VARCHAR(100) NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    applied_at TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_job_applications_user_job UNIQUE (user_id, job_id),
    CONSTRAINT ck_job_applications_status CHECK (
        status IN ('interested', 'applied', 'screening', 'interview', 'offer', 'rejected', 'withdrawn')
    )
);

CREATE INDEX IF NOT EXISTS ix_job_applications_user_updated
    ON job_applications (user_id, updated_at DESC);
