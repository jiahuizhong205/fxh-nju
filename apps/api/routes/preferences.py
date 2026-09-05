"""账号级偏好设置 API。"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import User
from apps.api.routes.auth import get_current_user

router = APIRouter()


class LearningReminderPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = True
    time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    frequency: Literal["每日浇水", "隔日浇水", "每周浇水", "仅工作日", "自定义"] = "每日浇水"
    week_days: list[int] = Field(default_factory=list, max_length=7)


class JobPushPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool = True
    job_types: list[str] = Field(default_factory=list, max_length=20)
    locations: list[str] = Field(default_factory=list, max_length=20)
    industries: list[str] = Field(default_factory=list, max_length=20)


class VisibilityPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["仅自己", "仅好友", "同专业同学", "全校公开"] = "仅自己"
    show_course: StrictBool = True
    show_grade: StrictBool = False
    show_timetable: StrictBool = True


class PreferencesData(BaseModel):
    """账号偏好的版本化 schema，保留通知页目前使用的中文标签键。"""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    notifications: dict[Annotated[str, Field(min_length=1, max_length=50)], StrictBool] | None = Field(
        default=None, max_length=20
    )
    learning_reminder: LearningReminderPreferences | None = None
    job_push: JobPushPreferences | None = None
    visibility: VisibilityPreferences | None = None


class PreferencesUpdate(BaseModel):
    preferences: PreferencesData = Field(default_factory=PreferencesData)


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
