"""账号数据同步检查点 API。"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import (
    JobFavorite,
    LearningPlan,
    LearningRecord,
    Job,
    RecommendationReport,
    StudentProfile,
    SyncRecord,
    User,
    utcnow,
)
from apps.api.routes.auth import get_current_user
from apps.api.routes.profile import ProfileUpdate

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


class SyncImportRequest(BaseModel):
    snapshot: dict = Field(min_length=1)
    scopes: list[SyncScope] = Field(default_factory=list, max_length=len(ALL_SCOPES))
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    confirm: StrictBool = False


def _validate_snapshot(snapshot: dict) -> tuple[bool, str]:
    if snapshot.get("schema_version") != 1:
        return False, "不支持的同步快照版本"
    scopes = snapshot.get("scopes")
    if not isinstance(scopes, dict):
        return False, "同步快照缺少 scopes"
    if set(scopes) - set(ALL_SCOPES):
        return False, "同步快照包含未知范围"
    if not isinstance(snapshot.get("account", {}), dict):
        return False, "同步快照 account 格式不正确"
    return True, "ok"


def _profile_import_values(raw: dict, existing: StudentProfile | None = None) -> dict | None:
    """把导入画像交给统一 schema 校验，并排除版本/时间等服务端字段。"""
    if not isinstance(raw, dict):
        return None
    allowed = {
        "major", "grade", "campus", "interests", "strengths", "career_goals",
        "math_willingness", "campus_flexibility", "credit_budget", "certificate_goal",
        "schedule_preferences",
    }
    values = {
        "major": existing.major if existing else "",
        "grade": existing.grade if existing else "",
        "campus": existing.campus if existing else "",
        "interests": existing.interests if existing else [],
        "strengths": existing.strengths if existing else [],
        "career_goals": existing.career_goals if existing else "",
        "math_willingness": existing.math_willingness if existing else False,
        "campus_flexibility": existing.campus_flexibility if existing else False,
        "credit_budget": existing.credit_budget if existing else 0,
        "certificate_goal": existing.certificate_goal if existing else "",
        "schedule_preferences": existing.schedule_preferences if existing else {},
    }
    values.update({key: raw[key] for key in allowed if key in raw})
    if not all(isinstance(values.get(key), str) and values[key].strip() for key in ("major", "grade")):
        return None
    try:
        return ProfileUpdate.model_validate(values).model_dump()
    except Exception:
        return None


@router.post("/sync/import/preview")
async def preview_sync_import(payload: SyncImportRequest):
    """只校验快照结构并返回待导入范围，不修改数据库。"""
    valid, reason = _validate_snapshot(payload.snapshot)
    if not valid:
        return {"valid": False, "reason": reason, "scopes": []}
    requested = payload.scopes or list(ALL_SCOPES)
    available = [scope for scope in requested if scope in payload.snapshot.get("scopes", {})]
    return {
        "valid": True,
        "schema_version": payload.snapshot["schema_version"],
        "request_id": str(payload.request_id),
        "scopes": available,
        "requires_confirmation": True,
    }


@router.post("/sync/import")
async def import_sync_snapshot(
    payload: SyncImportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确认后合并脱敏快照；重复请求不会重复导入。"""
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="请先预览并确认同步快照")
    valid, reason = _validate_snapshot(payload.snapshot)
    if not valid:
        raise HTTPException(status_code=400, detail=reason)

    requested = payload.scopes or list(ALL_SCOPES)
    snapshot_scopes = payload.snapshot.get("scopes", {})
    records = await _load_records(db, user.id)
    now = utcnow()
    counts = {scope: {"added": 0, "updated": 0, "skipped": 0} for scope in requested}
    updated_records: list[SyncRecord] = []

    for scope in requested:
        record = records.get(scope)
        if record and _is_duplicate_request(record, payload.request_id):
            counts[scope]["skipped"] = 1
            continue
        raw_scope = snapshot_scopes.get(scope)

        if scope == "profile" and isinstance(raw_scope, dict):
            result = await db.execute(
                select(StudentProfile)
                .where(StudentProfile.user_id == user.id)
                .order_by(StudentProfile.updated_at.desc())
                .limit(1)
            )
            profile = result.scalar_one_or_none()
            values = _profile_import_values(raw_scope, profile)
            if values is None:
                counts[scope]["skipped"] = 1
            elif profile:
                for key, value in values.items():
                    setattr(profile, key, value)
                profile.version += 1
                profile.updated_at = now
                counts[scope]["updated"] = 1
            else:
                db.add(StudentProfile(user_id=user.id, **values))
                counts[scope]["added"] = 1

        elif scope == "job_favorites" and isinstance(raw_scope, list):
            existing_result = await db.execute(
                select(JobFavorite.job_id).where(JobFavorite.user_id == user.id)
            )
            existing_ids = set(existing_result.scalars().all())
            for item in raw_scope[:100]:
                job_id = item.get("job_id") if isinstance(item, dict) else item
                if not isinstance(job_id, str) or job_id in existing_ids or not await db.get(Job, job_id):
                    counts[scope]["skipped"] += 1
                    continue
                db.add(JobFavorite(user_id=user.id, job_id=job_id))
                existing_ids.add(job_id)
                counts[scope]["added"] += 1

        elif scope == "learning_records" and isinstance(raw_scope, list):
            result = await db.execute(
                select(LearningRecord).where(LearningRecord.user_id == user.id)
            )
            existing = {
                (item.course_name, item.term): item
                for item in result.scalars().all()
            }
            for item in raw_scope[:100]:
                if not isinstance(item, dict):
                    counts[scope]["skipped"] += 1
                    continue
                key = (item.get("course_name"), item.get("term"))
                try:
                    credits = float(item.get("credits"))
                except (TypeError, ValueError):
                    credits = 0
                if not isinstance(key[0], str) or not isinstance(key[1], str) or credits <= 0:
                    counts[scope]["skipped"] += 1
                    continue
                values = {
                    "course_code": str(item.get("course_code", ""))[:50],
                    "credits": credits,
                    "status": item.get("status", "completed"),
                    "grade": item.get("grade"),
                    "source": "sync_import",
                }
                if values["status"] not in {"completed", "in_progress", "planned"}:
                    counts[scope]["skipped"] += 1
                    continue
                current = existing.get(key)
                if current:
                    for field, value in values.items():
                        setattr(current, field, value)
                    current.updated_at = now
                    counts[scope]["updated"] += 1
                else:
                    db.add(LearningRecord(
                        user_id=user.id,
                        course_name=key[0][:200],
                        term=key[1][:30],
                        **values,
                    ))
                    counts[scope]["added"] += 1

        elif scope == "learning_plans" and isinstance(raw_scope, list):
            for item in raw_scope[:20]:
                if not isinstance(item, dict) or not isinstance(item.get("program"), str):
                    counts[scope]["skipped"] += 1
                    continue
                db.add(LearningPlan(
                    user_id=user.id,
                    program_name=item["program"][:200],
                    profile_version=int(item.get("profile_version", 0) or 0),
                    status="draft",
                    items=item.get("items", []) if isinstance(item.get("items", []), list) else [],
                    alternatives=item.get("alternatives", []) if isinstance(item.get("alternatives", []), list) else [],
                    warnings=item.get("warnings", []) if isinstance(item.get("warnings", []), list) else [],
                    infeasible=bool(item.get("infeasible", False)),
                    schedule_analysis=item.get("schedule_analysis", {}) if isinstance(item.get("schedule_analysis", {}), dict) else {},
                ))
                counts[scope]["added"] += 1

        elif scope == "recommendation_reports" and isinstance(raw_scope, list):
            for item in raw_scope[:20]:
                if not isinstance(item, dict):
                    counts[scope]["skipped"] += 1
                    continue
                db.add(RecommendationReport(
                    user_id=user.id,
                    profile_version=int(item.get("profile_version", 0) or 0),
                    profile_snapshot=item.get("profile_snapshot", {}) if isinstance(item.get("profile_snapshot", {}), dict) else {},
                    recommendations=item.get("recommendations", []) if isinstance(item.get("recommendations", []), list) else [],
                    is_stale=True,
                ))
                counts[scope]["added"] += 1

        if record:
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
        updated_records.append(record)

    account = payload.snapshot.get("account", {})
    if isinstance(account, dict) and isinstance(account.get("preferences"), dict):
        user.preferences = account["preferences"]
        if isinstance(account.get("onboarding_completed"), bool):
            user.onboarding_completed = account["onboarding_completed"]

    await db.commit()
    for record in updated_records:
        await db.refresh(record)
    return {
        "status": "synced",
        "request_id": str(payload.request_id),
        "counts": counts,
        "records": [_serialize(record) for record in updated_records],
    }


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
