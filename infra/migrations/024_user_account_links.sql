CREATE TABLE IF NOT EXISTS user_account_links (
    id UUID PRIMARY KEY,
    owner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    linked_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_account_links_pair UNIQUE (owner_user_id, linked_user_id),
    CONSTRAINT ck_user_account_links_not_self CHECK (owner_user_id <> linked_user_id)
);

CREATE INDEX IF NOT EXISTS ix_user_account_links_owner
    ON user_account_links (owner_user_id, created_at DESC);
