"""账号数据同步检查点 API。"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import SyncRecord, User, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()

SyncScope = Literal[
    "profile",
    "recommendation_reports",
    "learning_plans",
    "job_favorites",
    "learning_records",
]
ALL_SCOPES: tuple[str, ...] = (
    "profile",
    "recommendation_reports",
    "learning_plans",
    "job_favorites",
    "learning_records",
)


class SyncRequest(BaseModel):
    scopes: list[SyncScope] = Field(default_factory=list, max_length=len(ALL_SCOPES))
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)


def _serialize(record: SyncRecord) -> dict:
    return {
        "scope": record.scope,
        "version": record.version,
        "status": record.status,
        "error": record.error,
        "request_id": record.last_request_id or None,
        "retry_count": record.retry_count or 0,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _is_duplicate_request(record: SyncRecord, request_id: uuid.UUID) -> bool:
    return bool(record.last_request_id) and record.last_request_id == str(request_id)


async def _load_records(db: AsyncSession, user_id) -> dict[str, SyncRecord]:
    result = await db.execute(select(SyncRecord).where(SyncRecord.user_id == user_id))
    return {record.scope: record for record in result.scalars().all()}


@router.get("/sync/status")
async def sync_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    records = await _load_records(db, user.id)
    return {
        "records": [
            _serialize(records[scope]) if scope in records else {
                "scope": scope,
                "version": 0,
                "status": "pending",
                "error": "",
                "request_id": None,
                "retry_count": 0,
                "started_at": None,
                "completed_at": None,
                "updated_at": None,
            }
            for scope in ALL_SCOPES
        ]
    }


@router.post("/sync")
async def sync_data(
    payload: SyncRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scopes = payload.scopes or list(ALL_SCOPES)
    now = utcnow()
    records = await _load_records(db, user.id)
    updated: list[SyncRecord] = []
    for scope in scopes:
        record = records.get(scope)
        if record:
            if not _is_duplicate_request(record, payload.request_id):
                record.version += 1
                record.status = "synced"
                record.error = ""
                record.started_at = now
                record.completed_at = now
                record.last_request_id = str(payload.request_id)
                record.retry_count = (record.retry_count or 0) + 1
                record.updated_at = now
        else:
            record = SyncRecord(
                user_id=user.id,
                scope=scope,
                version=1,
                status="synced",
                last_request_id=str(payload.request_id),
                retry_count=1,
                started_at=now,
                completed_at=now,
                updated_at=now,
            )
            db.add(record)
        updated.append(record)
    await db.commit()
    for record in updated:
        await db.refresh(record)
    return {"records": [_serialize(record) for record in updated], "status": "synced"}
