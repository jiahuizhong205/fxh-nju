CREATE TABLE IF NOT EXISTS user_friendships (
    id UUID PRIMARY KEY,
    requester_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    addressee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP NULL,
    CONSTRAINT uq_user_friendships_pair UNIQUE (requester_id, addressee_id),
    CONSTRAINT ck_user_friendships_not_self CHECK (requester_id <> addressee_id)
);
CREATE INDEX IF NOT EXISTS ix_user_friendships_requester ON user_friendships (requester_id, status);
CREATE INDEX IF NOT EXISTS ix_user_friendships_addressee ON user_friendships (addressee_id, status);
