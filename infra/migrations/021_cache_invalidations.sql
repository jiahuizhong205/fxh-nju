CREATE TABLE IF NOT EXISTS cache_invalidations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope VARCHAR(30) NOT NULL,
    generation INTEGER NOT NULL DEFAULT 0,
    last_cleared_at TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cache_invalidations_user_scope UNIQUE (user_id, scope)
);

CREATE INDEX IF NOT EXISTS ix_cache_invalidations_user
    ON cache_invalidations (user_id, scope);
