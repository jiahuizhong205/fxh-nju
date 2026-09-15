"""Transactional, user-scoped persistence for long-term memories."""

import asyncio
import math
from collections.abc import Sequence
from typing import get_args
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models import UserMemory, utcnow
from services.memory.extraction import MemoryCandidate, MemoryCategory
from services.memory.security import normalize_memory_text, sanitize_memory_text
from services.rag.retrieval import embed_text, embedding_signature


_SEMANTIC_DUPLICATE_THRESHOLD = 0.92
_MEMORY_CATEGORIES = frozenset(get_args(MemoryCategory))


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) == 0:
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _canonical_key_for_category(category: str, canonical_key: str) -> str:
    prefix = f"{category}:"
    key = normalize_memory_text(canonical_key).lower()
    if ":" in key:
        key = key.split(":", 1)[1]
    key = key.strip(":-_ ") or "general"
    return f"{prefix}{key[:max(1, 300 - len(prefix))]}"


async def _prepared_candidate(candidate: MemoryCandidate):
    content = sanitize_memory_text(
        candidate.content,
        explicitly_requested=candidate.explicitly_requested,
    )
    if not content:
        return None
    canonical_key = _canonical_key_for_category(
        candidate.category, candidate.canonical_key,
    )
    if settings.mock_llm:
        return candidate, content, canonical_key, None, ""
    embedding = await asyncio.to_thread(embed_text, content)
    return candidate, content, canonical_key, embedding, embedding_signature()


async def _first_memory(db: AsyncSession, statement):
    result = await db.execute(statement)
    return result.scalars().first()


async def _same_category_memories(
    db: AsyncSession,
    user_id: UUID,
    category: str,
) -> list[UserMemory]:
    result = await db.execute(
        select(UserMemory)
        .where(
            UserMemory.user_id == user_id,
            UserMemory.category == category,
        )
        .with_for_update()
    )
    return list(result.scalars().all())


def _dialect_name(db: AsyncSession) -> str:
    bind = db.get_bind()
    return str(getattr(getattr(bind, "dialect", None), "name", ""))


async def _acquire_semantic_lock(
    db: AsyncSession,
    user_id: UUID,
    category: str,
) -> None:
    if _dialect_name(db) != "postgresql":
        return
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"user-memory:{user_id}:{category}"},
    )


def _postgres_upsert_statement(values: dict):
    statement = postgresql_insert(UserMemory).values(**values)
    excluded = statement.excluded
    return statement.on_conflict_do_update(
        index_elements=[UserMemory.user_id, UserMemory.canonical_key],
        set_={
            "category": excluded.category,
            "content": excluded.content,
            "importance": excluded.importance,
            "confidence": excluded.confidence,
            "source_message_id": excluded.source_message_id,
            "source_conversation_id": excluded.source_conversation_id,
            "embedding": excluded.embedding,
            "embedding_provider": excluded.embedding_provider,
            "updated_at": excluded.updated_at,
        },
    )


async def _find_merge_target(
    db: AsyncSession,
    user_id: UUID,
    candidate: MemoryCandidate,
    content: str,
    canonical_key: str,
    embedding: Sequence[float] | None,
    signature: str,
) -> UserMemory | None:
    exact = await _first_memory(
        db,
        select(UserMemory)
        .where(
            UserMemory.user_id == user_id,
            UserMemory.canonical_key == canonical_key,
        )
        .with_for_update(),
    )
    if exact is not None:
        return exact

    normalized = normalize_memory_text(content).casefold()
    for memory in await _same_category_memories(db, user_id, candidate.category):
        if settings.mock_llm:
            if normalize_memory_text(memory.content).casefold() == normalized:
                return memory
            continue
        if (
            embedding is not None
            and memory.embedding is not None
            and memory.embedding_provider == signature
            and _cosine_similarity(embedding, memory.embedding)
            >= _SEMANTIC_DUPLICATE_THRESHOLD
        ):
            return memory
    return None


async def _upsert_one_candidate(
    db: AsyncSession,
    user_id: UUID,
    prepared,
    source_conversation_id: UUID,
    source_message_id: UUID,
) -> None:
    candidate, content, canonical_key, embedding, signature = prepared
    memory = await _find_merge_target(
        db,
        user_id,
        candidate,
        content,
        canonical_key,
        embedding,
        signature,
    )
    now = utcnow()
    if memory is None:
        values = dict(
            id=uuid4(),
            user_id=user_id,
            canonical_key=canonical_key,
            category=candidate.category,
            content=content,
            importance=candidate.importance,
            confidence=candidate.confidence,
            source_message_id=source_message_id,
            source_conversation_id=source_conversation_id,
            embedding=embedding,
            embedding_provider=signature,
            created_at=now,
            updated_at=now,
        )
        if _dialect_name(db) == "postgresql":
            await db.execute(_postgres_upsert_statement(values))
        else:
            db.add(UserMemory(**values))
        return

    memory.category = candidate.category
    memory.content = content
    memory.importance = candidate.importance
    memory.confidence = candidate.confidence
    memory.source_message_id = source_message_id
    memory.source_conversation_id = source_conversation_id
    memory.embedding = embedding
    memory.embedding_provider = signature
    memory.updated_at = now


async def upsert_memory_candidates(
    db: AsyncSession,
    user_id: UUID,
    candidates: Sequence[MemoryCandidate],
    source_conversation_id: UUID,
    source_message_id: UUID,
) -> int:
    """Atomically merge safe candidates into one user's memory rows."""
    prepared = []
    for candidate in candidates:
        value = await _prepared_candidate(candidate)
        if value is not None:
            prepared.append(value)

    try:
        for category in sorted({value[0].category for value in prepared}):
            await _acquire_semantic_lock(db, user_id, category)
        for value in prepared:
            await _upsert_one_candidate(
                db,
                user_id,
                value,
                source_conversation_id,
                source_message_id,
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return len(prepared)


async def update_user_memory(
    db: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
    *,
    category: str | None = None,
    content: str | None = None,
    importance: float | None = None,
    explicitly_requested: bool = False,
) -> UserMemory | None:
    """Update one memory only when it belongs to the specified user."""
    if category is not None and category not in _MEMORY_CATEGORIES:
        raise ValueError("unsupported memory category")
    if importance is not None and not 0.0 <= importance <= 1.0:
        raise ValueError("memory importance must be between 0 and 1")

    safe_content = None
    if content is not None:
        safe_content = sanitize_memory_text(
            content,
            explicitly_requested=explicitly_requested,
        )
        if not safe_content:
            raise ValueError("memory content is not safe to store")

    try:
        memory = await _first_memory(
            db,
            select(UserMemory)
            .where(
                UserMemory.id == memory_id,
                UserMemory.user_id == user_id,
            )
            .with_for_update(),
        )
        if memory is None:
            # End the read transaction without expiring callers' already-loaded
            # ORM objects; no mutation or provider work has occurred.
            await db.commit()
            return None

        embedding = None
        signature = ""
        if safe_content is not None and not settings.mock_llm:
            embedding = await asyncio.to_thread(embed_text, safe_content)
            signature = embedding_signature()

        values = {"updated_at": utcnow()}
        effective_category = category or memory.category
        if category is not None or safe_content is not None:
            values["canonical_key"] = (
                f"{effective_category}:manual-{memory_id.hex}"
            )
        if category is not None and category != memory.category:
            values["category"] = category
        if safe_content is not None:
            values["content"] = safe_content
            values["embedding"] = embedding
            values["embedding_provider"] = signature
        if importance is not None:
            values["importance"] = importance
        result = await db.execute(
            update(UserMemory)
            .where(
                UserMemory.id == memory_id,
                UserMemory.user_id == user_id,
            )
            .values(**values)
        )
        if not result.rowcount:
            await db.rollback()
            return None
        refreshed = await _first_memory(
            db,
            select(UserMemory)
            .where(
                UserMemory.id == memory_id,
                UserMemory.user_id == user_id,
            )
            .execution_options(populate_existing=True),
        )
        await db.commit()
        return refreshed
    except Exception:
        await db.rollback()
        raise


async def delete_user_memory(
    db: AsyncSession,
    user_id: UUID,
    memory_id: UUID,
) -> bool:
    """Hard-delete the body and vector together in one user-scoped transaction."""
    try:
        result = await db.execute(
            delete(UserMemory).where(
                UserMemory.id == memory_id,
                UserMemory.user_id == user_id,
            )
        )
        await db.commit()
        return bool(result.rowcount)
    except Exception:
        await db.rollback()
        raise
