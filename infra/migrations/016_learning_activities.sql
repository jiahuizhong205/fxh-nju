CREATE TABLE IF NOT EXISTS learning_activities (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity_date DATE NOT NULL,
    minutes INTEGER NOT NULL DEFAULT 0,
    source VARCHAR(50) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_learning_activities_user_date UNIQUE (user_id, activity_date)
);

CREATE INDEX IF NOT EXISTS ix_learning_activities_user_date
    ON learning_activities (user_id, activity_date DESC);
