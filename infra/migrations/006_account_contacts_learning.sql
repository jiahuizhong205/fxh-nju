CREATE TABLE IF NOT EXISTS user_contacts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_type VARCHAR(20) NOT NULL,
    value VARCHAR(200) NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_contacts_value UNIQUE (user_id, contact_type, value)
);

CREATE INDEX IF NOT EXISTS ix_user_contacts_user_id ON user_contacts (user_id);

CREATE TABLE IF NOT EXISTS learning_records (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_name VARCHAR(200) NOT NULL,
    course_code VARCHAR(50) NOT NULL DEFAULT '',
    term VARCHAR(30) NOT NULL,
    credits DOUBLE PRECISION NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    grade DOUBLE PRECISION,
    source VARCHAR(50) NOT NULL DEFAULT 'manual',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_learning_records_course_term UNIQUE (user_id, course_name, term)
);

CREATE INDEX IF NOT EXISTS ix_learning_records_user_id ON learning_records (user_id);
