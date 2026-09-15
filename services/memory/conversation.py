"""Assemble bounded chat context without splitting completed turns."""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models import ConversationSummary, Message


_MESSAGE_SEPARATOR = "\n\n"
@dataclass(frozen=True)
class MessageSnapshot:
    id: UUID
    role: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class ChatTurn:
    users: tuple[MessageSnapshot, ...]
    assistant: MessageSnapshot

    @property
    def messages(self) -> tuple[MessageSnapshot, ...]:
        return (*self.users, self.assistant)


@dataclass(frozen=True)
class ConversationContext:
    messages: tuple[object, ...]
    summary: str
    summary_candidates: tuple[MessageSnapshot, ...]


def group_turns(
    messages: Sequence[MessageSnapshot],
) -> tuple[list[ChatTurn], tuple[MessageSnapshot, ...]]:
    """Split chronological messages into answered turns and the trailing user segment."""
    turns: list[ChatTurn] = []
    pending_users: list[MessageSnapshot] = []
    for message in messages:
        if message.role == "user":
            pending_users.append(message)
        elif message.role == "assistant" and pending_users:
            turns.append(ChatTurn(users=tuple(pending_users), assistant=message))
            pending_users = []
    pending = tuple(pending_users)
    return turns, pending


def _message_size(messages: Sequence[MessageSnapshot]) -> int:
    return len(_MESSAGE_SEPARATOR.join(message.content for message in messages))


def _as_langchain_messages(messages: Sequence[MessageSnapshot]):
    from langchain_core.messages import AIMessage, HumanMessage

    return tuple(
        AIMessage(content=message.content)
        if message.role == "assistant"
        else HumanMessage(content=message.content)
        for message in messages
    )


def assemble_conversation_context(
    messages: Sequence[MessageSnapshot],
    summary: str,
    recent_turn_limit: int,
    character_budget: int,
) -> ConversationContext:
    """Keep the latest user segment and as many newest full turns as fit."""
    turns, pending = group_turns(messages)
    selected = list(pending)
    selected_turn_count = 0

    for turn in reversed(turns):
        if selected_turn_count >= max(recent_turn_limit, 0):
            break
        candidate = [*turn.messages, *selected]
        if _message_size(candidate) > character_budget:
            break
        selected = candidate
        selected_turn_count += 1

    summary_candidates = tuple(
        snapshot
        for turn in turns[:len(turns) - selected_turn_count]
        for snapshot in turn.messages
    )

    result = _as_langchain_messages(selected)
    context_size = len(_MESSAGE_SEPARATOR.join(message.content for message in result))
    separator_size = len(_MESSAGE_SEPARATOR) if result else 0
    bounded_summary = (
        summary
        if summary and len(summary) + separator_size + context_size <= character_budget
        else ""
    )

    return ConversationContext(
        messages=result,
        summary=bounded_summary,
        summary_candidates=summary_candidates,
    )


async def load_conversation_context(
    db: AsyncSession,
    conversation_id: UUID,
) -> ConversationContext:
    """Read the stored summary and chronological messages for one conversation."""
    summary_result = await db.execute(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
    )
    summary_row = summary_result.scalar_one_or_none()

    snapshots = await load_message_snapshots(db, conversation_id)
    return assemble_conversation_context(
        snapshots,
        summary=str(summary_row.summary or "") if summary_row else "",
        recent_turn_limit=settings.chat_recent_turn_limit,
        character_budget=settings.chat_context_character_budget,
    )


async def load_message_snapshots(
    db: AsyncSession,
    conversation_id: UUID,
) -> tuple[MessageSnapshot, ...]:
    """Share the chronological snapshot read between chat and summary refresh."""
    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return tuple(
        MessageSnapshot(
            id=row.id,
            role=row.role,
            content=str(row.content or ""),
            created_at=row.created_at,
        )
        for row in messages_result.scalars().all()
    )
