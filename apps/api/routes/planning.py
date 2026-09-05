"""规划域 REST API——专业目录 / 推荐 / 课程规划 / 岗位。

数据源已落库（Program/ProgramPlanItem/Job），REST 层从 DB 读。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import StudentProfile, Program, ProgramPlanItem, Course, Job, JobFavorite, User
from apps.api.routes.auth import get_current_user
from services.planning.recommendation_engine import recommend
from services.planning.course_planner import generate_plan, PROGRAM_PLANS
from services.planning.career_engine import match_jobs

router = APIRouter()


class RecommendRequest(BaseModel):
    profile: dict | None = None  # 缺省时读取最新画像


async def _latest_profile(db: AsyncSession, user_id) -> dict | None:
    result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user_id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    p = result.scalar_one_or_none()
    if not p:
        return None
    return {
        "major": p.major, "grade": p.grade, "campus": p.campus,
        "interests": p.interests or [], "strengths": p.strengths or [],
        "career_goals": p.career_goals,
        "math_willingness": p.math_willingness,
        "campus_flexibility": p.campus_flexibility,
        "credit_budget": p.credit_budget,
        "certificate_goal": p.certificate_goal,
        "schedule_preferences": p.schedule_preferences or {},
    }


async def _load_programs(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Program))
    progs = result.scalars().all()
    plan_names = set((await db.execute(select(ProgramPlanItem.program_name).distinct())).scalars())
    # Keep the currently supported built-in templates discoverable until the
    # corresponding database plan rows are imported. DB rows still take
    # precedence when present and are never overwritten here.
    plan_names.update(PROGRAM_PLANS.keys())
    return [{
        "name": p.name, "total_credits": p.total_credits, "campus": p.campus,
        "subject_rank": p.subject_rank, "core_courses": p.core_courses or [],
        "required_math": p.required_math, "required_math_level": p.required_math_level,
        "semesters_needed": p.semesters_needed, "discipline": p.discipline,
        "has_plan": p.name in plan_names,
    } for p in progs]


async def _load_plans(db: AsyncSession) -> dict[str, list[dict]]:
    result = await db.execute(select(ProgramPlanItem).order_by(ProgramPlanItem.semester))
    items = result.scalars().all()
    plans: dict[str, list[dict]] = {}
    for it in items:
        plans.setdefault(it.program_name, []).append({
            "semester": it.semester, "term": it.term,
            "course": it.course, "credits": it.credits, "campus": it.campus,
        })
    return plans


def _job_dict(j) -> dict:
    return {
        "id": j.id, "employer": j.employer, "title": j.title, "location": j.location,
        "majors": j.majors or [], "preferred_cross": j.preferred_cross or [],
        "skills_required": j.skills_required or [], "skills_preferred": j.skills_preferred or [],
        "deadline": j.deadline, "source": j.source,
    }


async def _load_jobs(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Job))
    return [_job_dict(j) for j in result.scalars().all()]


@router.get("/programs")
async def list_programs(db: AsyncSession = Depends(get_db)):
    return {"programs": await _load_programs(db)}


@router.post("/recommend")
async def recommend_programs(
    req: RecommendRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = req.profile or await _latest_profile(db, user.id)
    if not profile:
        raise HTTPException(status_code=400, detail="尚未填写学生画像")
    programs = [p for p in await _load_programs(db) if p["has_plan"]]
    return {"recommendations": recommend(profile, programs)}


@router.get("/programs/plan")
async def course_plan(
    program: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = await _latest_profile(db, user.id) or {}
    db_plans = await _load_plans(db)
    plans = {**PROGRAM_PLANS, **db_plans}
    result = generate_plan(program, profile, plans)
    if not result.items:
        raise HTTPException(status_code=404, detail=f"未找到「{program}」的培养方案")
    return {
        "program": result.program_name,
        "items": [_plan_item(it) for it in result.items],
        "alternatives": [[_plan_item(it) for it in alt] for alt in result.alternatives],
        "warnings": result.warnings,
        "infeasible": result.infeasible,
    }


def _plan_item(it) -> dict:
    return {
        "semester": it.semester, "term": it.term, "year": it.year,
        "course": it.course, "credits": it.credits, "campus": it.campus,
    }


def _course_dict(c) -> dict:
    return {
        "teaching_class_id": c.teaching_class_id,
        "course_number": c.course_number,
        "course_name": c.course_name,
        "teacher": c.teacher,
        "credit": c.credit,
        "hours": c.hours,
        "campus": c.campus,
        "department": c.department,
        "teaching_place": c.teaching_place,
        "school_term": c.school_term,
    }


@router.get("/programs/{name}/courses")
async def program_courses(name: str, db: AsyncSession = Depends(get_db)):
    """某辅修专业对应的可选课程（按院系关联 Course）。"""
    prog = await db.get(Program, name)
    if not prog:
        raise HTTPException(status_code=404, detail=f"未找到「{name}」")
    result = await db.execute(
        select(Course).where(Course.department == prog.department).order_by(Course.course_name)
    )
    return {
        "program": name,
        "department": prog.department,
        "courses": [_course_dict(c) for c in result.scalars().all()],
    }


@router.get("/jobs")
async def list_jobs(major: str | None = None, minor: str | None = None, db: AsyncSession = Depends(get_db)):
    jobs = await _load_jobs(db)
    if major:
        return {"jobs": match_jobs(major, minor, jobs)}
    return {"jobs": jobs}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return {"job": _job_dict(job)}


@router.get("/favorites/jobs")
async def list_job_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobFavorite)
        .where(JobFavorite.user_id == user.id)
        .order_by(JobFavorite.created_at.desc())
    )
    return {"job_ids": [favorite.job_id for favorite in result.scalars().all()]}


@router.put("/favorites/jobs/{job_id}")
async def add_job_favorite(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")

    result = await db.execute(
        select(JobFavorite).where(
            JobFavorite.user_id == user.id,
            JobFavorite.job_id == job_id,
        )
    )
    if not result.scalar_one_or_none():
        db.add(JobFavorite(user_id=user.id, job_id=job_id))
        await db.commit()
    return {"job_id": job_id, "favorited": True}


@router.delete("/favorites/jobs/{job_id}")
async def remove_job_favorite(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobFavorite).where(
            JobFavorite.user_id == user.id,
            JobFavorite.job_id == job_id,
        )
    )
    favorite = result.scalar_one_or_none()
    if favorite:
        await db.delete(favorite)
        await db.commit()
    return {"job_id": job_id, "favorited": False}
