"""Authenticated, user-scoped management API for long-term memories."""

import asyncio
import base64
import binascii
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.database import get_db
from apps.api.models import User, UserMemory, utcnow
from apps.api.routes.auth import get_current_user
from services.memory.extraction import MemoryCategory
from services.memory.security import classify_memory_sensitivity, sanitize_memory_text
from services.memory.store import delete_user_memory, update_user_memory
from services.rag.retrieval import embed_text, embedding_signature


router = APIRouter()
logger = logging.getLogger("fuxiaohe.memory.api")

_CURSOR_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")
_MAX_CURSOR_CHARACTERS = 1024


class MemoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory
    content: str = Field(min_length=1, max_length=500)
    importance: float = Field(default=0.5, ge=0, le=1)


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory | None = None
    content: str | None = Field(default=None, min_length=1, max_length=500)
    importance: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def require_change(self):
        if self.category is None and self.content is None and self.importance is None:
            raise ValueError("at least one non-null memory field is required")
        return self


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: MemoryCategory
    content: str
    importance: float
    source_conversation_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class MemoryPage(BaseModel):
    items: list[MemoryResponse]
    next_cursor: str | None


def _manual_content_or_422(content: str) -> str:
    """Treat an authenticated manual save as explicit intent, never for credentials."""
    if classify_memory_sensitivity(content) == "credential":
        raise HTTPException(status_code=422, detail="该内容包含不能保存的认证秘密")
    safe_content = sanitize_memory_text(content, explicitly_requested=True)
    if not safe_content:
        raise HTTPException(status_code=422, detail="记忆内容不能为空或不适合保存")
    return safe_content


def _encode_cursor(updated_at: datetime, memory_id: uuid.UUID) -> str:
    payload = json.dumps(
        {"updated_at": updated_at.isoformat(), "id": str(memory_id)},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        if (
            not cursor
            or len(cursor) > _MAX_CURSOR_CHARACTERS
            or not _CURSOR_RE.fullmatch(cursor)
        ):
            raise ValueError("invalid base64 cursor")
        unpadded = cursor.rstrip("=")
        padding = "=" * (-len(unpadded) % 4)
        decoded = base64.b64decode(
            unpadded + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded.decode("utf-8"))
        if type(payload) is not dict or set(payload) != {"updated_at", "id"}:
            raise ValueError("invalid cursor fields")
        if type(payload["updated_at"]) is not str or type(payload["id"]) is not str:
            raise ValueError("invalid cursor field types")
        if "T" not in payload["updated_at"]:
            raise ValueError("cursor timestamp must be an ISO datetime")
        updated_at = datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
        if updated_at.tzinfo is not None:
            updated_at = updated_at.astimezone(timezone.utc).replace(tzinfo=None)
        memory_id = uuid.UUID(payload["id"])
    except (
        ValueError,
        OverflowError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ):
        raise HTTPException(status_code=422, detail="记忆分页游标不合法") from None
    return updated_at, memory_id


async def _owned_memory(
    db: AsyncSession,
    user_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> UserMemory | None:
    result = await db.execute(
        select(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.user_id == user_id,
        )
    )
    return result.scalars().first()


def _response(memory: UserMemory) -> MemoryResponse:
    return MemoryResponse.model_validate(memory)


async def _raise_safe_database_error(
    db: AsyncSession,
    *,
    operation: str,
    user_id: uuid.UUID,
    memory_id: uuid.UUID | None,
    error: Exception,
) -> None:
    try:
        await db.rollback()
    except Exception as rollback_error:
        logger.error(
            "memory api rollback failed operation=%s user_id=%s memory_id=%s error_type=%s",
            operation,
            user_id,
            memory_id,
            type(rollback_error).__name__,
        )
    logger.error(
        "memory api database operation failed operation=%s user_id=%s memory_id=%s error_type=%s",
        operation,
        user_id,
        memory_id,
        type(error).__name__,
    )
    raise HTTPException(status_code=500, detail="记忆服务暂时不可用") from None


@router.get("/memories", response_model=MemoryPage)
async def list_memories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    category: MemoryCategory | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> MemoryPage:
    statement = select(UserMemory).where(UserMemory.user_id == user.id)
    if category is not None:
        statement = statement.where(UserMemory.category == category)
    if cursor is not None:
        cursor_updated_at, cursor_id = _decode_cursor(cursor)
        statement = statement.where(or_(
            UserMemory.updated_at < cursor_updated_at,
            and_(
                UserMemory.updated_at == cursor_updated_at,
                UserMemory.id < cursor_id,
            ),
        ))
    try:
        result = await db.execute(
            statement.order_by(UserMemory.updated_at.desc(), UserMemory.id.desc()).limit(limit + 1)
        )
    except Exception as exc:
        await _raise_safe_database_error(
            db,
            operation="list",
            user_id=user.id,
            memory_id=None,
            error=exc,
        )
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_cursor(items[-1].updated_at, items[-1].id) if has_more else None
    return MemoryPage(items=[_response(item) for item in items], next_cursor=next_cursor)


@router.post("/memories", response_model=MemoryResponse, status_code=201)
async def create_memory(
    payload: MemoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    content = _manual_content_or_422(payload.content)
    memory_id = uuid.uuid4()
    try:
        embedding = None
        signature = ""
        if not settings.mock_llm:
            embedding = await asyncio.to_thread(embed_text, content)
            signature = embedding_signature()

        now = utcnow()
        memory = UserMemory(
            id=memory_id,
            user_id=user.id,
            canonical_key=f"{payload.category}:manual-{memory_id.hex}",
            category=payload.category,
            content=content,
            importance=payload.importance,
            confidence=1.0,
            source_message_id=None,
            source_conversation_id=None,
            embedding=embedding,
            embedding_provider=signature,
            created_at=now,
            updated_at=now,
        )
        db.add(memory)
        await db.commit()
    except Exception as exc:
        await _raise_safe_database_error(
            db,
            operation="create",
            user_id=user.id,
            memory_id=memory_id,
            error=exc,
        )
    return _response(memory)


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    try:
        memory = await _owned_memory(db, user.id, memory_id)
    except Exception as exc:
        await _raise_safe_database_error(
            db,
            operation="get",
            user_id=user.id,
            memory_id=memory_id,
            error=exc,
        )
    if memory is None:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return _response(memory)


@router.patch("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryResponse:
    content = None
    if payload.content is not None:
        content = _manual_content_or_422(payload.content)
    try:
        memory = await update_user_memory(
            db,
            user.id,
            memory_id,
            category=payload.category,
            content=content,
            importance=payload.importance,
            explicitly_requested=True,
        )
    except Exception as exc:
        await _raise_safe_database_error(
            db,
            operation="update",
            user_id=user.id,
            memory_id=memory_id,
            error=exc,
        )
    if memory is None:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return _response(memory)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        deleted = await delete_user_memory(db, user.id, memory_id)
    except Exception as exc:
        await _raise_safe_database_error(
            db,
            operation="delete",
            user_id=user.id,
            memory_id=memory_id,
            error=exc,
        )
    if not deleted:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return Response(status_code=204)
