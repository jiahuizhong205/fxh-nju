CREATE TABLE IF NOT EXISTS knowledge_progress (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    node_id VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'todo',
    progress_percent INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_knowledge_progress_user_node UNIQUE (user_id, node_id),
    CONSTRAINT ck_knowledge_progress_status CHECK (status IN ('todo', 'progress', 'done', 'mastered')),
    CONSTRAINT ck_knowledge_progress_percent CHECK (progress_percent BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS ix_knowledge_progress_user_updated
    ON knowledge_progress (user_id, updated_at DESC);
