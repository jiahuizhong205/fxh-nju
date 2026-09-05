CREATE TABLE IF NOT EXISTS learning_plans (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    program_name VARCHAR(200) NOT NULL,
    profile_version INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    items JSONB NOT NULL DEFAULT '[]'::jsonb,
    alternatives JSONB NOT NULL DEFAULT '[]'::jsonb,
    warnings JSONB NOT NULL DEFAULT '[]'::jsonb,
    infeasible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_learning_plans_status CHECK (status IN ('draft', 'adopted', 'archived'))
);

CREATE INDEX IF NOT EXISTS ix_learning_plans_user_updated
    ON learning_plans (user_id, updated_at DESC);
