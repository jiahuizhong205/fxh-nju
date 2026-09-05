"""账号附属数据 API——联系方式和学习记录。"""

import re
import hashlib
import secrets
import uuid
from datetime import date, timedelta
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import LearningActivity, LearningPlan, LearningRecord, Program, User, UserContact, VerificationChallenge, utcnow
from apps.api.config import settings
from apps.api.routes.auth import get_current_user

router = APIRouter()

VERIFICATION_REQUEST_COOLDOWN_SECONDS = 60


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


class VerificationCodeInput(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordResetRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    contact_type: Literal["phone", "email"]


class PasswordResetConfirm(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    contact_type: Literal["phone", "email"]
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    new_password: str


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


def _hash_verification_code(code: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _new_verification_code() -> tuple[str, str, str]:
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    return code, salt, _hash_verification_code(code, salt)


def _challenge_request_allowed(created_at, now=None) -> bool:
    """限制同一联系方式的验证码申请频率，避免供应商接口被刷。"""
    if created_at is None:
        return True
    now = now or utcnow()
    return (now - created_at).total_seconds() >= VERIFICATION_REQUEST_COOLDOWN_SECONDS


def _verification_provider_payload(
    contact_type: str,
    contact_value: str,
    code: str,
    purpose: str,
) -> dict:
    return {
        "channel": contact_type,
        "to": contact_value,
        "code": code,
        "purpose": purpose,
    }


async def _deliver_verification_code(
    challenge: VerificationChallenge,
    contact: UserContact,
    code: str,
) -> str:
    """向可选 provider 投递验证码；未配置时保留 queued，不泄露验证码。"""
    provider_url = settings.verification_provider_url.strip()
    if not provider_url:
        return "queued"
    challenge.delivery_attempts = (challenge.delivery_attempts or 0) + 1
    try:
        headers = {}
        if settings.verification_provider_api_key:
            headers["Authorization"] = f"Bearer {settings.verification_provider_api_key}"
        async with httpx.AsyncClient(timeout=settings.verification_provider_timeout_seconds) as client:
            response = await client.post(
                provider_url,
                json=_verification_provider_payload(contact.contact_type, contact.value, code, challenge.purpose),
                headers=headers,
            )
            response.raise_for_status()
    except Exception as exc:
        challenge.delivery_status = "failed"
        challenge.delivery_error = str(exc)[:2000]
        challenge.updated_at = utcnow()
        return "failed"
    challenge.delivery_status = "sent"
    challenge.delivery_error = ""
    challenge.delivered_at = utcnow()
    challenge.updated_at = utcnow()
    return "sent"


def _verify_challenge_code(challenge: VerificationChallenge, code: str, now=None) -> tuple[bool, str]:
    now = now or utcnow()
    attempts = challenge.attempts or 0
    max_attempts = challenge.max_attempts or 5
    if challenge.consumed:
        return False, "验证码已失效"
    if now >= challenge.expires_at:
        challenge.consumed = True
        return False, "验证码已过期"
    if attempts >= max_attempts:
        challenge.consumed = True
        return False, "验证码尝试次数过多"
    challenge.attempts = attempts + 1
    if secrets.compare_digest(challenge.code_hash, _hash_verification_code(code, challenge.code_salt)):
        challenge.consumed = True
        return True, "ok"
    if challenge.attempts >= max_attempts:
        challenge.consumed = True
    return False, "验证码错误"


def _challenge_purpose_clause(purpose: str):
    return VerificationChallenge.purpose == purpose


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


def _calculate_completion_percent(completed_credits: float, target_credits: float) -> int:
    if target_credits <= 0:
        return 0
    return min(100, max(0, round(completed_credits / target_credits * 100)))


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
    elif payload.is_primary and contact.verified:
        contact.is_primary = True

    if payload.is_primary and contact.verified:
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


@router.post("/auth/contacts/{contact_id}/verification-code")
async def request_contact_verification_code(
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
    if contact.verified:
        return {"status": "already_verified", "contact": _serialize_contact(contact)}

    latest_result = await db.execute(
        select(VerificationChallenge)
        .where(
            VerificationChallenge.contact_id == contact.id,
            VerificationChallenge.user_id == user.id,
            _challenge_purpose_clause("contact_verification"),
        )
        .order_by(VerificationChallenge.created_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    if latest and not _challenge_request_allowed(latest.created_at):
        raise HTTPException(status_code=429, detail="验证码发送过于频繁，请稍后再试")

    previous = await db.execute(
        select(VerificationChallenge).where(
            VerificationChallenge.contact_id == contact.id,
            VerificationChallenge.user_id == user.id,
            VerificationChallenge.consumed.is_(False),
            _challenge_purpose_clause("contact_verification"),
        )
    )
    for challenge in previous.scalars().all():
        challenge.consumed = True
        challenge.updated_at = utcnow()

    code, salt, digest = _new_verification_code()
    challenge = VerificationChallenge(
        user_id=user.id,
        contact_id=contact.id,
        code_hash=digest,
        code_salt=salt,
        purpose="contact_verification",
        expires_at=utcnow() + timedelta(minutes=10),
        delivery_status="queued",
    )
    db.add(challenge)
    await db.flush()
    delivery_status = await _deliver_verification_code(challenge, contact, code)
    await db.commit()
    await db.refresh(challenge)
    return {
        "status": "sent_to_provider" if delivery_status == "sent" else "queued_for_delivery",
        "delivery_channel": contact.contact_type,
        "delivery_status": delivery_status,
        "expires_at": challenge.expires_at.isoformat(),
        "message": "验证码已提交投递" if delivery_status == "sent" else "验证码已进入投递队列，待配置短信/邮件服务后发送",
    }


@router.post("/auth/contacts/{contact_id}/verify")
async def verify_contact(
    contact_id: uuid.UUID,
    payload: VerificationCodeInput,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contact_result = await db.execute(
        select(UserContact).where(UserContact.id == contact_id, UserContact.user_id == user.id)
    )
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="联系方式不存在")
    if contact.verified:
        return {"status": "already_verified", "contact": _serialize_contact(contact)}

    challenge_result = await db.execute(
        select(VerificationChallenge)
        .where(
            VerificationChallenge.contact_id == contact.id,
            VerificationChallenge.user_id == user.id,
            _challenge_purpose_clause("contact_verification"),
        )
        .order_by(VerificationChallenge.created_at.desc())
        .limit(1)
    )
    challenge = challenge_result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    ok, reason = _verify_challenge_code(challenge, payload.code)
    if not ok:
        challenge.updated_at = utcnow()
        await db.commit()
        raise HTTPException(status_code=400, detail=reason)

    contact.verified = True
    if not contact.is_primary:
        verified_primary = await db.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == contact.contact_type,
                UserContact.verified.is_(True),
                UserContact.is_primary.is_(True),
                UserContact.id != contact.id,
            )
        )
        if not verified_primary.scalar_one_or_none():
            contact.is_primary = True
    contact.updated_at = utcnow()
    challenge.updated_at = utcnow()
    await db.commit()
    await db.refresh(contact)
    return {"status": "verified", "contact": _serialize_contact(contact)}


@router.post("/auth/password-reset/request")
async def request_password_reset(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """为已验证联系方式创建找回密码挑战，不泄露账号是否存在。"""
    result = await db.execute(select(User).where(User.username == payload.username.strip()))
    target = result.scalar_one_or_none()
    if target:
        contact_result = await db.execute(select(UserContact).where(
            UserContact.user_id == target.id,
            UserContact.contact_type == payload.contact_type,
            UserContact.verified.is_(True),
            UserContact.is_primary.is_(True),
        ))
        contact = contact_result.scalar_one_or_none()
        if contact:
            latest_result = await db.execute(select(VerificationChallenge).where(
                VerificationChallenge.user_id == target.id,
                VerificationChallenge.contact_id == contact.id,
                _challenge_purpose_clause("password_reset"),
            ).order_by(VerificationChallenge.created_at.desc()).limit(1))
            latest = latest_result.scalar_one_or_none()
            if latest and not _challenge_request_allowed(latest.created_at):
                return {"status": "accepted", "message": "如果账号存在且联系方式已验证，验证码将进入投递队列"}

            previous = await db.execute(select(VerificationChallenge).where(
                VerificationChallenge.user_id == target.id,
                VerificationChallenge.contact_id == contact.id,
                _challenge_purpose_clause("password_reset"),
                VerificationChallenge.consumed.is_(False),
            ))
            for challenge in previous.scalars().all():
                challenge.consumed = True
            code, salt, digest = _new_verification_code()
            challenge = VerificationChallenge(
                user_id=target.id,
                contact_id=contact.id,
                code_hash=digest,
                code_salt=salt,
                purpose="password_reset",
                expires_at=utcnow() + timedelta(minutes=10),
                delivery_status="queued",
            )
            db.add(challenge)
            await db.flush()
            await _deliver_verification_code(challenge, contact, code)
            await db.commit()
    # 无论账号、联系方式是否存在，都返回相同文案，降低枚举风险。
    return {"status": "accepted", "message": "如果账号存在且联系方式已验证，验证码将进入投递队列"}


@router.post("/auth/password-reset/confirm")
async def confirm_password_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    _validate_password(payload.new_password)
    result = await db.execute(select(User).where(User.username == payload.username.strip()))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=400, detail="验证码或账号信息不正确")
    contact_result = await db.execute(select(UserContact).where(
        UserContact.user_id == target.id,
        UserContact.contact_type == payload.contact_type,
        UserContact.verified.is_(True),
        UserContact.is_primary.is_(True),
    ))
    contact = contact_result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=400, detail="验证码或账号信息不正确")
    challenge_result = await db.execute(
        select(VerificationChallenge)
        .where(
            VerificationChallenge.user_id == target.id,
            VerificationChallenge.contact_id == contact.id,
            _challenge_purpose_clause("password_reset"),
        )
        .order_by(VerificationChallenge.created_at.desc())
        .limit(1)
    )
    challenge = challenge_result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    ok, reason = _verify_challenge_code(challenge, payload.code)
    if not ok:
        await db.commit()
        raise HTTPException(status_code=400, detail=reason)
    await _revoke_user_sessions(db, target.id)
    target.salt, target.password_hash = _hash_password(payload.new_password)
    target.token = None
    await db.commit()
    return {"status": "ok", "message": "密码已重置，请重新登录"}


@router.post("/auth/contacts/{contact_id}/primary")
async def set_primary_contact(
    contact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserContact).where(
        UserContact.id == contact_id,
        UserContact.user_id == user.id,
    ))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="联系方式不存在")
    if not contact.verified:
        raise HTTPException(status_code=400, detail="未验证的联系方式不能设为主联系方式")
    others = await db.execute(select(UserContact).where(
        UserContact.user_id == user.id,
        UserContact.contact_type == contact.contact_type,
        UserContact.id != contact.id,
    ))
    for other in others.scalars().all():
        other.is_primary = False
    contact.is_primary = True
    contact.updated_at = utcnow()
    await db.commit()
    await db.refresh(contact)
    return {"contact": _serialize_contact(contact), "status": "primary"}


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
    was_primary = contact.is_primary
    contact_type = contact.contact_type
    await db.delete(contact)
    if was_primary:
        replacement = await db.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == contact_type,
                UserContact.verified.is_(True),
                UserContact.id != contact.id,
            ).order_by(UserContact.created_at)
        )
        next_contact = replacement.scalars().first()
        if next_contact:
            next_contact.is_primary = True
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
    plan_result = await db.execute(
        select(LearningPlan)
        .where(LearningPlan.user_id == user.id, LearningPlan.status == "adopted")
        .order_by(LearningPlan.updated_at.desc())
        .limit(1)
    )
    adopted_plan = plan_result.scalar_one_or_none()
    target_credits = 0
    plan_program = None
    if adopted_plan:
        plan_program = adopted_plan.program_name
        program = await db.get(Program, adopted_plan.program_name)
        target_credits = program.total_credits if program else sum(
            float(item.get("credits", 0)) for item in adopted_plan.items or []
        )
    record_summary = _summarize_learning_records(records)
    return {
        **record_summary,
        **_summarize_learning_activities(activities),
        "target_credits": target_credits,
        "completion_percent": _calculate_completion_percent(
            record_summary["completed_credits"], target_credits
        ),
        "plan_program": plan_program,
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
