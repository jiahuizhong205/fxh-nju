from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from pgvector.sqlalchemy import Vector

from apps.api.config import settings

engine = create_async_engine(settings.database_url, pool_size=10, max_overflow=5)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all does not alter an already initialized database. Keep this
        # small compatibility migration here so existing Docker volumes get
        # the ownership column without losing any conversation data.
        if conn.dialect.name == "postgresql":
            await conn.execute(text(
                "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS "
                "user_id UUID REFERENCES users(id) ON DELETE CASCADE"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_user_id "
                "ON conversations (user_id)"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "preferences JSONB NOT NULL DEFAULT '{}'::jsonb"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "is_admin BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            await conn.execute(text(
                "ALTER TABLE recommendation_reports ADD COLUMN IF NOT EXISTS "
                "is_stale BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            await conn.execute(text(
                "ALTER TABLE recommendation_reports ADD COLUMN IF NOT EXISTS "
                "sync_fingerprint VARCHAR(64) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE learning_plans ADD COLUMN IF NOT EXISTS "
                "sync_fingerprint VARCHAR(64) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS remote_type VARCHAR(50) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_type VARCHAR(50) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS arrival_time VARCHAR(100) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS internship_duration VARCHAR(100) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS responsibilities JSONB NOT NULL DEFAULT '[]'::jsonb"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS application_email VARCHAR(200) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS application_note TEXT NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'received'"
            ))
            await conn.execute(text(
                "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            ))
            await conn.execute(text(
                "ALTER TABLE courses ADD COLUMN IF NOT EXISTS schedule JSONB NOT NULL DEFAULT '[]'::jsonb"
            ))
            await conn.execute(text(
                "ALTER TABLE learning_plans ADD COLUMN IF NOT EXISTS "
                "schedule_analysis JSONB NOT NULL DEFAULT '{}'::jsonb"
            ))
            await conn.execute(text(
                "ALTER TABLE sync_records ADD COLUMN IF NOT EXISTS "
                "last_request_id VARCHAR(64) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE sync_records ADD COLUMN IF NOT EXISTS "
                "retry_count INTEGER NOT NULL DEFAULT 0"
            ))
            await conn.execute(text(
                "ALTER TABLE sync_records ADD COLUMN IF NOT EXISTS "
                "provider_status VARCHAR(20) NOT NULL DEFAULT 'disabled'"
            ))
            await conn.execute(text(
                "ALTER TABLE sync_records ADD COLUMN IF NOT EXISTS "
                "provider_error TEXT NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE sync_records ADD COLUMN IF NOT EXISTS "
                "provider_synced_at TIMESTAMP NULL"
            ))
            await conn.execute(text(
                "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS "
                "risk_level VARCHAR(20) NOT NULL DEFAULT 'normal'"
            ))
            await conn.execute(text(
                "ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS "
                "risk_reason VARCHAR(50) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE verification_challenges ADD COLUMN IF NOT EXISTS "
                "purpose VARCHAR(30) NOT NULL DEFAULT 'contact_verification'"
            ))
            await conn.execute(text(
                "ALTER TABLE verification_challenges ADD COLUMN IF NOT EXISTS "
                "delivery_status VARCHAR(20) NOT NULL DEFAULT 'queued'"
            ))
            await conn.execute(text(
                "ALTER TABLE verification_challenges ADD COLUMN IF NOT EXISTS "
                "delivery_attempts INTEGER NOT NULL DEFAULT 0"
            ))
            await conn.execute(text(
                "ALTER TABLE verification_challenges ADD COLUMN IF NOT EXISTS "
                "delivery_error TEXT NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE verification_challenges ADD COLUMN IF NOT EXISTS "
                "delivered_at TIMESTAMP NULL"
            ))
            await conn.execute(text(
                "ALTER TABLE verification_challenges ADD COLUMN IF NOT EXISTS "
                "provider_message_id VARCHAR(200) NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE feedback_attachments ADD COLUMN IF NOT EXISTS "
                "storage_backend VARCHAR(30) NOT NULL DEFAULT 'database'"
            ))
            await conn.execute(text(
                "ALTER TABLE feedback_attachments ADD COLUMN IF NOT EXISTS "
                "storage_key TEXT NOT NULL DEFAULT ''"
            ))
            await conn.execute(text(
                "ALTER TABLE feedback_attachments ADD COLUMN IF NOT EXISTS "
                "scan_status VARCHAR(20) NOT NULL DEFAULT 'clean'"
            ))
            await conn.execute(text(
                "ALTER TABLE courses ADD COLUMN IF NOT EXISTS "
                "capacity INTEGER NOT NULL DEFAULT 0"
            ))
            await conn.execute(text(
                "ALTER TABLE courses ADD COLUMN IF NOT EXISTS "
                "enrolled_count INTEGER NOT NULL DEFAULT 0"
            ))
