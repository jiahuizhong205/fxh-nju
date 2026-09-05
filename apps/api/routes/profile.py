"""学生画像 API——CRUD 用户画像。"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import RecommendationReport, StudentProfile, User, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()


class SchedulePreferences(BaseModel):
    """排课页面和冲突处理页面共用的结构化偏好。"""

    model_config = ConfigDict(extra="forbid")

    energy_period: Literal["晨光", "黄金档", "暮色"] | None = None
    time_slots: list[Literal["早八战士", "上午黄金档", "午后时光", "晚间高效派", "随意灵活"]] = Field(
        default_factory=list, max_length=5
    )
    concentration: Literal["集中授课", "均匀分散", "每周几天高强度其余自由"] | None = None
    nap: Literal["需要午休", "午休灵活", "无需午休"] | None = None
    prefer_late: StrictBool = False
    conflict_strategies: list[
        Literal[
            "免修不免考申请",
            "跨校区通勤",
            "优先选择线上/混合课程",
            "放弃冲突课程/延后修读",
            "申请课程替换/学分互认",
        ]
    ] = Field(default_factory=list, max_length=5)


class ProfileUpdate(BaseModel):
    major: str
    grade: str
    campus: str = ""
    interests: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    career_goals: str = ""
    math_willingness: bool = False
    campus_flexibility: bool = False
    credit_budget: int = 0
    certificate_goal: str = ""
    schedule_preferences: SchedulePreferences = Field(default_factory=SchedulePreferences)


@router.get("/profile")
async def get_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前登录用户的画像。"""
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user.id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {"profile": None}
    return {"profile": _serialize(profile)}


@router.put("/profile")
async def upsert_profile(payload: ProfileUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """创建或更新当前登录用户的画像。"""
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user.id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()

    data = payload.model_dump()
    if profile:
        for k, v in data.items():
            setattr(profile, k, v)
        profile.version += 1
        profile.updated_at = utcnow()
        await db.execute(
            update(RecommendationReport)
            .where(
                RecommendationReport.user_id == user.id,
                RecommendationReport.is_stale.is_(False),
            )
            .values(is_stale=True)
        )
    else:
        profile = StudentProfile(**data, user_id=user.id)
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return {"profile": _serialize(profile)}


@router.delete("/profile")
async def delete_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """清空当前登录用户的画像。"""
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user.id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if profile:
        await db.delete(profile)
        await db.commit()
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="无画像可删除")


def _serialize(p: StudentProfile) -> dict:
    return {
        "id": str(p.id),
        "major": p.major,
        "grade": p.grade,
        "campus": p.campus,
        "interests": p.interests or [],
        "strengths": p.strengths or [],
        "career_goals": p.career_goals,
        "math_willingness": p.math_willingness,
        "campus_flexibility": p.campus_flexibility,
        "credit_budget": p.credit_budget,
        "certificate_goal": p.certificate_goal,
        "schedule_preferences": p.schedule_preferences or {},
        "version": p.version,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
