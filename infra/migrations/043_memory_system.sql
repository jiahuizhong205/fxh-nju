CREATE TABLE conversation_summaries (
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    summarized_through_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL,
    revision INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_memories (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    canonical_key VARCHAR(300) NOT NULL,
    category VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    importance DOUBLE PRECISION NOT NULL DEFAULT 0,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
    source_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL,
    source_conversation_id UUID NULL REFERENCES conversations(id) ON DELETE SET NULL,
    embedding vector(1024),
    embedding_provider VARCHAR(100) NOT NULL DEFAULT '',
    last_used_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, canonical_key)
);

CREATE INDEX ix_user_memories_user_category
  ON user_memories(user_id, category);
CREATE INDEX ix_user_memories_user_updated
  ON user_memories(user_id, updated_at DESC, id DESC);
