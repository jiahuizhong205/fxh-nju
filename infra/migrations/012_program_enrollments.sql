CREATE TABLE IF NOT EXISTS program_enrollments (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    program_name VARCHAR(200) NOT NULL REFERENCES programs(name) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_program_enrollments_user_program UNIQUE (user_id, program_name),
    CONSTRAINT ck_program_enrollments_status CHECK (status IN ('active', 'left'))
);

CREATE INDEX IF NOT EXISTS ix_program_enrollments_program_status
    ON program_enrollments (program_name, status);
