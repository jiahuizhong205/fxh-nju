"""学生画像 API——CRUD 用户画像。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import StudentProfile, User, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()


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
    schedule_preferences: dict = Field(default_factory=dict)


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
