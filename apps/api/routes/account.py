"""账号附属数据 API——联系方式和学习记录。"""

import re
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import LearningActivity, LearningRecord, User, UserContact, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()


class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contact_type: Literal["phone", "email"]
    value: str = Field(min_length=5, max_length=200)
    is_primary: bool = False

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_contact(self):
        _normalize_contact(self.contact_type, self.value)
        return self


class LearningRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_name: str = Field(min_length=1, max_length=200)
    course_code: str = Field(default="", max_length=50)
    term: str = Field(min_length=1, max_length=30)
    credits: float = Field(gt=0, le=20)
    status: str = "completed"
    grade: float | None = Field(default=None, ge=0, le=100)
    source: str = Field(default="manual", max_length=50)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"completed", "in_progress", "planned"}:
            raise ValueError("课程状态不合法")
        return value


class LearningActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_date: date | None = None
    minutes: int = Field(gt=0, le=1440)
    source: str = Field(default="manual", max_length=50)


def _normalize_contact(contact_type: str, value: str) -> str:
    value = value.strip()
    if contact_type == "phone":
        value = re.sub(r"[\s-]", "", value)
        if not re.fullmatch(r"1[3-9]\d{9}", value):
            raise ValueError("手机号格式不正确")
        return value
    value = value.lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("邮箱格式不正确")
    return value


def _mask_contact(contact_type: str, value: str) -> str:
    if contact_type == "phone":
        return f"{value[:3]}****{value[-4:]}"
    local, domain = value.split("@", 1)
    return f"{local[:1]}*****@{domain}"


def _serialize_contact(contact: UserContact) -> dict:
    return {
        "id": str(contact.id),
        "contact_type": contact.contact_type,
        "value": _mask_contact(contact.contact_type, contact.value),
        "verified": contact.verified,
        "is_primary": contact.is_primary,
    }


def _serialize_learning_record(record: LearningRecord) -> dict:
    return {
        "id": str(record.id),
        "course_name": record.course_name,
        "course_code": record.course_code,
        "term": record.term,
        "credits": record.credits,
        "status": record.status,
        "grade": record.grade,
        "source": record.source,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _summarize_learning_records(records: list[LearningRecord]) -> dict:
    summary = {"completed_credits": 0.0, "in_progress_credits": 0.0, "planned_credits": 0.0}
    for record in records:
        key = f"{record.status}_credits"
        if key in summary:
            summary[key] += record.credits
    summary["total_credits"] = sum(summary.values())
    return summary


def _summarize_learning_activities(activities: list[LearningActivity], today: date | None = None) -> dict:
    today = today or utcnow().date()
    days = {activity.activity_date for activity in activities if activity.activity_date <= today}
    streak = 0
    cursor = today
    while cursor in days:
        streak += 1
        cursor = cursor.fromordinal(cursor.toordinal() - 1)
    return {"learning_days": len(days), "streak_days": streak}


@router.get("/auth/contacts")
async def list_contacts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserContact)
        .where(UserContact.user_id == user.id)
        .order_by(UserContact.is_primary.desc(), UserContact.created_at)
    )
    return {"contacts": [_serialize_contact(contact) for contact in result.scalars().all()]}


@router.post("/auth/contacts")
async def upsert_contact(
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        value = _normalize_contact(payload.contact_type, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await db.execute(
        select(UserContact).where(
            UserContact.user_id == user.id,
            UserContact.contact_type == payload.contact_type,
            UserContact.value == value,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        contact = UserContact(
            user_id=user.id,
            contact_type=payload.contact_type,
            value=value,
            is_primary=payload.is_primary,
        )
        db.add(contact)
    elif payload.is_primary:
        contact.is_primary = True

    if payload.is_primary:
        others = await db.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == payload.contact_type,
                UserContact.id != contact.id,
            )
        )
        for other in others.scalars().all():
            other.is_primary = False
    await db.commit()
    await db.refresh(contact)
    return {"contact": _serialize_contact(contact), "status": "pending_verification" if not contact.verified else "ok"}


@router.delete("/auth/contacts/{contact_id}")
async def delete_contact(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserContact).where(UserContact.id == contact_id, UserContact.user_id == user.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="联系方式不存在")
    await db.delete(contact)
    await db.commit()
    return {"status": "deleted"}


@router.get("/learning/progress")
async def learning_progress(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LearningRecord)
        .where(LearningRecord.user_id == user.id)
        .order_by(LearningRecord.updated_at.desc())
    )
    records = result.scalars().all()
    activity_result = await db.execute(
        select(LearningActivity).where(LearningActivity.user_id == user.id)
    )
    activities = activity_result.scalars().all()
    return {
        **_summarize_learning_records(records),
        **_summarize_learning_activities(activities),
        "records": [_serialize_learning_record(record) for record in records],
    }


@router.put("/learning/activities")
async def upsert_learning_activity(
    payload: LearningActivityInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    activity_date = payload.activity_date or utcnow().date()
    result = await db.execute(
        select(LearningActivity).where(
            LearningActivity.user_id == user.id,
            LearningActivity.activity_date == activity_date,
        )
    )
    activity = result.scalar_one_or_none()
    if activity:
        activity.minutes = payload.minutes
        activity.source = payload.source
        activity.updated_at = utcnow()
    else:
        activity = LearningActivity(
            user_id=user.id,
            activity_date=activity_date,
            minutes=payload.minutes,
            source=payload.source,
            updated_at=utcnow(),
        )
        db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return {
        "activity": {
            "id": str(activity.id),
            "activity_date": activity.activity_date.isoformat(),
            "minutes": activity.minutes,
            "source": activity.source,
        }
    }


@router.put("/learning/records")
async def upsert_learning_record(
    payload: LearningRecordInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningRecord).where(
            LearningRecord.user_id == user.id,
            LearningRecord.course_name == payload.course_name,
            LearningRecord.term == payload.term,
        )
    )
    record = result.scalar_one_or_none()
    data = payload.model_dump()
    if record:
        for key, value in data.items():
            setattr(record, key, value)
        record.updated_at = utcnow()
    else:
        record = LearningRecord(user_id=user.id, **data)
        db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"record": _serialize_learning_record(record)}


@router.delete("/learning/records/{record_id}")
async def delete_learning_record(
    record_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningRecord).where(LearningRecord.id == record_id, LearningRecord.user_id == user.id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="学习记录不存在")
    await db.delete(record)
    await db.commit()
    return {"status": "deleted"}
