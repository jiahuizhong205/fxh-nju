"""学生画像 API——CRUD 用户画像。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import StudentProfile

router = APIRouter()


@router.get("/profile")
async def get_profile(db: AsyncSession = Depends(get_db)):
    """获取当前画像（MVP 单用户，取最新记录）。"""
    result = await db.execute(
        select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return {"profile": None}
    return {"profile": _serialize(profile)}


@router.put("/profile")
async def upsert_profile(
    major: str,
    grade: str,
    campus: str = "",
    career_goals: str = "",
    math_willingness: bool = False,
    campus_flexibility: bool = False,
    credit_budget: int = 0,
    certificate_goal: str = "",
    db: AsyncSession = Depends(get_db),
):
    """创建或更新画像。"""
    result = await db.execute(
        select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
    )
    profile = result.scalar_one_or_none()

    if profile:
        profile.major = major
        profile.grade = grade
        profile.campus = campus
        profile.career_goals = career_goals
        profile.math_willingness = math_willingness
        profile.campus_flexibility = campus_flexibility
        profile.credit_budget = credit_budget
        profile.certificate_goal = certificate_goal
        profile.version += 1
    else:
        profile = StudentProfile(
            major=major, grade=grade, campus=campus,
            career_goals=career_goals,
            math_willingness=math_willingness,
            campus_flexibility=campus_flexibility,
            credit_budget=credit_budget,
            certificate_goal=certificate_goal,
        )
        db.add(profile)

    await db.commit()
    await db.refresh(profile)
    return {"profile": _serialize(profile)}


@router.delete("/profile")
async def delete_profile(db: AsyncSession = Depends(get_db)):
    """清空画像。MVP 单用户。"""
    result = await db.execute(
        select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
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
        "career_goals": p.career_goals,
        "math_willingness": p.math_willingness,
        "campus_flexibility": p.campus_flexibility,
        "credit_budget": p.credit_budget,
        "certificate_goal": p.certificate_goal,
        "version": p.version,
        "updated_at": p.updated_at.isoformat(),
    }
