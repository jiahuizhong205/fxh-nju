"""账号级偏好设置 API。"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import User
from apps.api.routes.auth import get_current_user

router = APIRouter()
memory_logger = logging.getLogger("fuxiaohe.memory.preferences")


class LearningReminderPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = True
    time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    frequency: Literal["每日浇水", "隔日浇水", "每周浇水", "仅工作日", "自定义"] = "每日浇水"
    week_days: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list, max_length=7)


class JobPushPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = True
    job_types: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)
    locations: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)
    industries: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)


class VisibilityPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["仅自己", "仅好友", "同专业同学", "全校公开"] = "仅自己"
    show_course: StrictBool = True
    show_grade: StrictBool = False
    show_timetable: StrictBool = True


class MemoryPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_capture_enabled: StrictBool = True


class MemoryPreferencesResponse(BaseModel):
    preferences: MemoryPreferences


class PreferencesData(BaseModel):
    """账号偏好的版本化 schema，保留通知页目前使用的中文标签键。"""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    notifications: dict[Annotated[str, Field(min_length=1, max_length=50)], StrictBool] = Field(
        default_factory=dict, max_length=20
    )
    learning_reminder: LearningReminderPreferences = Field(default_factory=LearningReminderPreferences)
    job_push: JobPushPreferences = Field(default_factory=JobPushPreferences)
    visibility: VisibilityPreferences = Field(default_factory=VisibilityPreferences)
    memory: MemoryPreferences = Field(default_factory=MemoryPreferences)


class PreferencesUpdate(BaseModel):
    preferences: PreferencesData = Field(default_factory=PreferencesData)


_SECTION_MODELS = {
    "learning_reminder": LearningReminderPreferences,
    "job_push": JobPushPreferences,
    "visibility": VisibilityPreferences,
    "memory": MemoryPreferences,
}


def _merge_preference_section(existing: dict, section: str, value: dict) -> dict:
    model = _SECTION_MODELS[section].model_validate(value)
    data = PreferencesData.model_validate(existing or {})
    setattr(data, section, model)
    return data.model_dump(exclude_none=True)


async def _save_preference_section(section: str, value: BaseModel, user: User, db: AsyncSession) -> dict:
    user.preferences = _merge_preference_section(
        user.preferences or {}, section, value.model_dump()
    )
    await db.commit()
    return getattr(value, "model_dump")()


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user)):
    return {"preferences": PreferencesData.model_validate(user.preferences or {}).model_dump(exclude_none=True)}


@router.put("/preferences")
async def update_preferences(
    payload: PreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.preferences = payload.preferences.model_dump(exclude_none=True)
    await db.commit()
    return {"preferences": user.preferences}


@router.get("/preferences/learning-reminder")
async def get_learning_reminder_preferences(user: User = Depends(get_current_user)):
    data = PreferencesData.model_validate(user.preferences or {})
    return {"preferences": data.learning_reminder.model_dump()}


@router.put("/preferences/learning-reminder")
async def save_learning_reminder_preferences(
    payload: LearningReminderPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"preferences": await _save_preference_section("learning_reminder", payload, user, db)}


@router.get("/preferences/job-push")
async def get_job_push_preferences(user: User = Depends(get_current_user)):
    data = PreferencesData.model_validate(user.preferences or {})
    return {"preferences": data.job_push.model_dump()}


@router.put("/preferences/job-push")
async def save_job_push_preferences(
    payload: JobPushPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"preferences": await _save_preference_section("job_push", payload, user, db)}


@router.get("/preferences/visibility")
async def get_visibility_preferences(user: User = Depends(get_current_user)):
    data = PreferencesData.model_validate(user.preferences or {})
    return {"preferences": data.visibility.model_dump()}


@router.put("/preferences/visibility")
async def save_visibility_preferences(
    payload: VisibilityPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"preferences": await _save_preference_section("visibility", payload, user, db)}


@router.get("/preferences/memory", response_model=MemoryPreferencesResponse)
async def get_memory_preferences(user: User = Depends(get_current_user)):
    existing = user.preferences if isinstance(user.preferences, dict) else {}
    memory = MemoryPreferences.model_validate(existing.get("memory") or {})
    return {"preferences": memory.model_dump()}


@router.put("/preferences/memory", response_model=MemoryPreferencesResponse)
async def save_memory_preferences(
    payload: MemoryPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    original = user.preferences
    existing = dict(original) if isinstance(original, dict) else {}
    existing["memory"] = payload.model_dump()
    user.preferences = existing
    try:
        await db.commit()
    except Exception as exc:
        try:
            await db.rollback()
        except Exception as rollback_exc:
            memory_logger.error(
                "memory preference rollback failed user_id=%s error_type=%s",
                user.id,
                type(rollback_exc).__name__,
            )
        user.preferences = original
        memory_logger.error(
            "memory preference write failed user_id=%s error_type=%s",
            user.id,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="记忆偏好暂时无法保存") from None
    return {"preferences": payload.model_dump()}
