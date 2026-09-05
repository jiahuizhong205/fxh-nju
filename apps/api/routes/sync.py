"""账号数据同步检查点 API。"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import (
    JobFavorite,
    LearningPlan,
    LearningRecord,
    RecommendationReport,
    StudentProfile,
    SyncRecord,
    User,
    utcnow,
)
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


def _serialize_snapshot(user: User, scopes: dict) -> dict:
    """构造脱敏同步快照；认证凭据和附件原文永远不进入快照。"""
    return {
        "schema_version": 1,
        "exported_at": utcnow().isoformat(),
        "account": {
            "username": user.username,
            "nickname": user.nickname,
            "onboarding_completed": bool(user.onboarding_completed),
            "preferences": user.preferences or {},
        },
        "scopes": scopes,
    }


def _is_duplicate_request(record: SyncRecord, request_id: uuid.UUID) -> bool:
    return bool(record.last_request_id) and record.last_request_id == str(request_id)


async def _load_records(db: AsyncSession, user_id) -> dict[str, SyncRecord]:
    result = await db.execute(select(SyncRecord).where(SyncRecord.user_id == user_id))
    return {record.scope: record for record in result.scalars().all()}


@router.get("/sync/export")
async def export_sync_snapshot(
    scopes: list[SyncScope] = Query(default=[]),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出账号级脱敏快照，供备份或外部同步适配器使用。"""
    requested = scopes or list(ALL_SCOPES)
    data: dict = {}

    if "profile" in requested:
        result = await db.execute(
            select(StudentProfile)
            .where(StudentProfile.user_id == user.id)
            .order_by(StudentProfile.updated_at.desc())
            .limit(1)
        )
        profile = result.scalar_one_or_none()
        data["profile"] = {
            "major": profile.major,
            "grade": profile.grade,
            "campus": profile.campus,
            "interests": profile.interests or [],
            "strengths": profile.strengths or [],
            "career_goals": profile.career_goals,
            "math_willingness": profile.math_willingness,
            "campus_flexibility": profile.campus_flexibility,
            "credit_budget": profile.credit_budget,
            "certificate_goal": profile.certificate_goal,
            "schedule_preferences": profile.schedule_preferences or {},
            "version": profile.version,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        } if profile else None

    if "recommendation_reports" in requested:
        result = await db.execute(
            select(RecommendationReport)
            .where(RecommendationReport.user_id == user.id)
            .order_by(RecommendationReport.created_at.desc())
            .limit(20)
        )
        data["recommendation_reports"] = [{
            "id": str(item.id),
            "profile_version": item.profile_version,
            "profile_snapshot": item.profile_snapshot or {},
            "recommendations": item.recommendations or [],
            "is_stale": item.is_stale,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        } for item in result.scalars().all()]

    if "learning_plans" in requested:
        result = await db.execute(
            select(LearningPlan)
            .where(LearningPlan.user_id == user.id)
            .order_by(LearningPlan.updated_at.desc())
            .limit(20)
        )
        data["learning_plans"] = [{
            "id": str(item.id),
            "program": item.program_name,
            "profile_version": item.profile_version,
            "status": item.status,
            "items": item.items or [],
            "alternatives": item.alternatives or [],
            "warnings": item.warnings or [],
            "infeasible": item.infeasible,
            "schedule_analysis": item.schedule_analysis or {},
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        } for item in result.scalars().all()]

    if "job_favorites" in requested:
        result = await db.execute(
            select(JobFavorite)
            .where(JobFavorite.user_id == user.id)
            .order_by(JobFavorite.created_at.desc())
        )
        data["job_favorites"] = [{
            "job_id": item.job_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        } for item in result.scalars().all()]

    if "learning_records" in requested:
        result = await db.execute(
            select(LearningRecord)
            .where(LearningRecord.user_id == user.id)
            .order_by(LearningRecord.updated_at.desc())
        )
        data["learning_records"] = [{
            "course_name": item.course_name,
            "course_code": item.course_code,
            "term": item.term,
            "credits": item.credits,
            "status": item.status,
            "grade": item.grade,
            "source": item.source,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        } for item in result.scalars().all()]

    return _serialize_snapshot(user, data)


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
