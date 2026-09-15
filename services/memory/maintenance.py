"""Bounded post-response maintenance for summaries and long-term memories."""

import asyncio
from dataclasses import dataclass
import logging
from time import perf_counter
from uuid import UUID

from sqlalchemy import select

from apps.api.config import settings
from apps.api.database import async_session
from apps.api.models import Conversation, Message, User
from services.memory.extraction import extract_memory_candidates
from services.memory.store import upsert_memory_candidates
from services.memory.summarizer import refresh_conversation_summary


logger = logging.getLogger("fuxiaohe.memory.maintenance")


@dataclass(frozen=True)
class _MaintenanceResult:
    summary_updated: bool = False
    summarized_message_count: int = 0
    auto_capture_enabled: bool = False
    candidate_count: int = 0
    upserted_count: int = 0


def memory_auto_capture_enabled(preferences: object) -> bool:
    """Read the consent flag conservatively while preserving the default-on schema."""
    if not isinstance(preferences, dict):
        return False
    memory = preferences.get("memory")
    if memory is None:
        return True
    if not isinstance(memory, dict):
        return False
    return memory.get("auto_capture_enabled", True) is True


async def _refresh_memory_state(
    conversation_id: UUID,
    user_id: UUID,
    latest_user_message_id: UUID,
    latest_assistant_message_id: UUID,
) -> _MaintenanceResult:
    summary = await refresh_conversation_summary(conversation_id)
    base_result = _MaintenanceResult(
        summary_updated=summary.updated,
        summarized_message_count=summary.summarized_message_count,
    )

    # Never retain the request-scoped session in a response background task.
    async with async_session() as db:
        conversation = await db.execute(
            select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        if conversation.scalar_one_or_none() is None:
            return base_result

        preference_result = await db.execute(
            select(User.preferences).where(User.id == user_id)
        )
        preferences = preference_result.scalar_one_or_none()
        capture_enabled = memory_auto_capture_enabled(preferences)
        if not capture_enabled:
            return base_result

        user_message_result = await db.execute(
            select(Message).where(
                Message.id == latest_user_message_id,
                Message.conversation_id == conversation_id,
                Message.role == "user",
            )
        )
        user_message = user_message_result.scalar_one_or_none()
        assistant_message_result = await db.execute(
            select(Message).where(
                Message.id == latest_assistant_message_id,
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
            )
        )
        assistant_message = assistant_message_result.scalar_one_or_none()
        if user_message is None or assistant_message is None:
            return _MaintenanceResult(
                summary_updated=base_result.summary_updated,
                summarized_message_count=base_result.summarized_message_count,
                auto_capture_enabled=True,
            )

        latest_user_text = str(user_message.content or "")
        latest_assistant_text = str(assistant_message.content or "")
        # Release read locks/connections while an external extraction model runs.
        await db.rollback()
        candidates = await extract_memory_candidates(
            latest_user_text,
            assistant_message=latest_assistant_text,
        )
        if not candidates:
            return _MaintenanceResult(
                summary_updated=base_result.summary_updated,
                summarized_message_count=base_result.summarized_message_count,
                auto_capture_enabled=True,
            )

        # Start a new transaction and lock the preference row through the memory
        # upsert commit. A preference update that committed during extraction is
        # therefore observed here; a concurrent update linearizes after this write.
        current_preference_result = await db.execute(
            select(User.preferences)
            .where(User.id == user_id)
            .with_for_update()
        )
        current_preferences = current_preference_result.scalar_one_or_none()
        if not memory_auto_capture_enabled(current_preferences):
            await db.rollback()
            return _MaintenanceResult(
                summary_updated=base_result.summary_updated,
                summarized_message_count=base_result.summarized_message_count,
                auto_capture_enabled=False,
                candidate_count=len(candidates),
            )

        upserted = await upsert_memory_candidates(
            db,
            user_id,
            candidates,
            conversation_id,
            latest_user_message_id,
        )
        return _MaintenanceResult(
            summary_updated=base_result.summary_updated,
            summarized_message_count=base_result.summarized_message_count,
            auto_capture_enabled=True,
            candidate_count=len(candidates),
            upserted_count=upserted,
        )


async def refresh_memory_state(
    conversation_id: UUID,
    user_id: UUID,
    latest_user_message_id: UUID,
    latest_assistant_message_id: UUID,
) -> None:
    """Run maintenance behind a timeout and contain all operational failures."""
    started_at = perf_counter()
    try:
        result = await asyncio.wait_for(
            _refresh_memory_state(
                conversation_id,
                user_id,
                latest_user_message_id,
                latest_assistant_message_id,
            ),
            timeout=settings.memory_background_timeout_seconds,
        )
    except TimeoutError:
        logger.warning(
            "memory maintenance timed out conversation_id=%s user_id=%s "
            "user_message_id=%s assistant_message_id=%s timeout_seconds=%s elapsed_ms=%.1f",
            conversation_id,
            user_id,
            latest_user_message_id,
            latest_assistant_message_id,
            settings.memory_background_timeout_seconds,
            (perf_counter() - started_at) * 1000,
        )
    except Exception as exc:
        logger.error(
            "memory maintenance failed conversation_id=%s user_id=%s "
            "user_message_id=%s assistant_message_id=%s error_type=%s elapsed_ms=%.1f",
            conversation_id,
            user_id,
            latest_user_message_id,
            latest_assistant_message_id,
            type(exc).__name__,
            (perf_counter() - started_at) * 1000,
        )
    else:
        logger.info(
            "memory maintenance completed conversation_id=%s user_id=%s "
            "user_message_id=%s assistant_message_id=%s summary_updated=%s "
            "summarized_message_count=%d auto_capture_enabled=%s candidate_count=%d "
            "upserted_count=%d elapsed_ms=%.1f",
            conversation_id,
            user_id,
            latest_user_message_id,
            latest_assistant_message_id,
            result.summary_updated,
            result.summarized_message_count,
            result.auto_capture_enabled,
            result.candidate_count,
            result.upserted_count,
            (perf_counter() - started_at) * 1000,
        )
