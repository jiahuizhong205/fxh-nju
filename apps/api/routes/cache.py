"""账号级缓存失效 API。

该接口只维护缓存命名空间的失效代次，不会删除对话、推荐报告等业务数据。
真实 Redis/对象存储缓存接入后，缓存消费者应以 generation 变化触发清理。
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import CacheInvalidation, User, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()

CacheScope = Literal["images", "conversations", "recommendations"]
ALL_SCOPES: tuple[str, ...] = ("images", "conversations", "recommendations")


class CacheClearRequest(BaseModel):
    scopes: list[CacheScope] = Field(default_factory=list, max_length=len(ALL_SCOPES))


def _serialize(record: CacheInvalidation | None, scope: str) -> dict:
    return {
        "scope": scope,
        "generation": record.generation if record else 0,
        "last_cleared_at": (
            record.last_cleared_at.isoformat() if record and record.last_cleared_at else None
        ),
    }


async def _load_records(db: AsyncSession, user_id) -> dict[str, CacheInvalidation]:
    result = await db.execute(select(CacheInvalidation).where(CacheInvalidation.user_id == user_id))
    return {record.scope: record for record in result.scalars().all()}


@router.get("/cache/status")
async def cache_status(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    records = await _load_records(db, user.id)
    return {"records": [_serialize(records.get(scope), scope) for scope in ALL_SCOPES]}


@router.post("/cache/clear")
async def clear_cache(
    payload: CacheClearRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scopes = payload.scopes or list(ALL_SCOPES)
    now = utcnow()
    records = await _load_records(db, user.id)
    cleared = []
    for scope in scopes:
        record = records.get(scope)
        if record:
            record.generation += 1
            record.last_cleared_at = now
            record.updated_at = now
        else:
            record = CacheInvalidation(
                user_id=user.id,
                scope=scope,
                generation=1,
                last_cleared_at=now,
                updated_at=now,
            )
            db.add(record)
        cleared.append(record)
    await db.commit()
    for record in cleared:
        await db.refresh(record)
    return {
        "status": "invalidated",
        "records": [_serialize(record, record.scope) for record in cleared],
        "message": "已发出缓存失效信号，未删除业务数据",
    }
