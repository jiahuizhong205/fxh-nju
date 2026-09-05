"""规划域 REST API——专业目录 / 推荐 / 课程规划 / 岗位。

数据源已落库（Program/ProgramPlanItem/Job），REST 层从 DB 读。
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import (
    StudentProfile, Program, ProgramPlanItem, Course, Job, JobFavorite,
    RecommendationReport, LearningPlan, JobApplication, ProgramEnrollment, User, utcnow,
)
from apps.api.routes.auth import get_current_user
from services.planning.recommendation_engine import recommend
from services.planning.course_planner import generate_plan, PROGRAM_PLANS
from services.planning.career_engine import match_jobs

router = APIRouter()


class RecommendRequest(BaseModel):
    profile: dict | None = None  # 缺省时读取最新画像


class SavePlanRequest(BaseModel):
    program: str
    adopt: bool = False


class PlanItemInput(BaseModel):
    semester: int = Field(ge=1, le=20)
    term: str = Field(min_length=1, max_length=20)
    year: int = Field(ge=1, le=10)
    course: str = Field(min_length=1, max_length=200)
    credits: float = Field(gt=0, le=20)
    campus: str = Field(default="", max_length=50)


class PlanUpdateRequest(BaseModel):
    items: list[PlanItemInput] = Field(min_length=1, max_length=100)


class JobApplicationUpdate(BaseModel):
    status: Literal["interested", "applied", "screening", "interview", "offer", "rejected", "withdrawn"]
    channel: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=2000)
    applied_at: datetime | None = None


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
        "version": p.version,
    }


async def _load_programs(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Program))
    progs = result.scalars().all()
    plan_names = set((await db.execute(select(ProgramPlanItem.program_name).distinct())).scalars())
    course_counts = dict(
        (row.program_name, row.course_count)
        for row in (
            await db.execute(
                select(ProgramPlanItem.program_name, func.count(ProgramPlanItem.id).label("course_count"))
                .group_by(ProgramPlanItem.program_name)
            )
        ).all()
    )
    participant_counts = dict(
        (row.program_name, row.participant_count)
        for row in (
            await db.execute(
                select(
                    ProgramEnrollment.program_name,
                    func.count(ProgramEnrollment.id).label("participant_count"),
                )
                .where(ProgramEnrollment.status == "active")
                .group_by(ProgramEnrollment.program_name)
            )
        ).all()
    )
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
        "course_count": course_counts.get(p.name, len(p.core_courses or [])),
        "participant_count": participant_counts.get(p.name, 0),
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
        "remote_type": j.remote_type,
        "job_type": j.job_type,
        "arrival_time": j.arrival_time,
        "internship_duration": j.internship_duration,
        "responsibilities": j.responsibilities or [],
        "application_email": j.application_email,
        "application_note": j.application_note,
    }


async def _load_jobs(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Job))
    return [_job_dict(j) for j in result.scalars().all()]


@router.get("/programs")
async def list_programs(db: AsyncSession = Depends(get_db)):
    return {"programs": await _load_programs(db)}


async def _participant_count(db: AsyncSession, program_name: str) -> int:
    result = await db.execute(
        select(func.count(ProgramEnrollment.id)).where(
            ProgramEnrollment.program_name == program_name,
            ProgramEnrollment.status == "active",
        )
    )
    return int(result.scalar_one())


@router.get("/programs/{program_name}/participants")
async def program_participants(program_name: str, db: AsyncSession = Depends(get_db)):
    if not await db.get(Program, program_name):
        raise HTTPException(status_code=404, detail=f"未找到「{program_name}」")
    return {"program": program_name, "participant_count": await _participant_count(db, program_name)}


@router.put("/programs/{program_name}/enrollment")
async def join_program(
    program_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(Program, program_name):
        raise HTTPException(status_code=404, detail=f"未找到「{program_name}」")
    result = await db.execute(
        select(ProgramEnrollment).where(
            ProgramEnrollment.user_id == user.id,
            ProgramEnrollment.program_name == program_name,
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment:
        enrollment.status = "active"
        enrollment.updated_at = utcnow()
    else:
        enrollment = ProgramEnrollment(user_id=user.id, program_name=program_name)
        db.add(enrollment)
    await db.commit()
    return {
        "program": program_name,
        "joined": True,
        "participant_count": await _participant_count(db, program_name),
    }


@router.delete("/programs/{program_name}/enrollment")
async def leave_program(
    program_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ProgramEnrollment).where(
            ProgramEnrollment.user_id == user.id,
            ProgramEnrollment.program_name == program_name,
        )
    )
    enrollment = result.scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="尚未加入该方向")
    enrollment.status = "left"
    enrollment.updated_at = utcnow()
    await db.commit()
    return {
        "program": program_name,
        "joined": False,
        "participant_count": await _participant_count(db, program_name),
    }


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
    recommendations = recommend(profile, programs)
    report = RecommendationReport(
        user_id=user.id,
        profile_version=profile.get("version", 0),
        profile_snapshot=profile,
        recommendations=recommendations,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return {
        "report_id": str(report.id),
        "generated_at": report.created_at.isoformat() if report.created_at else None,
        "recommendations": recommendations,
    }


@router.get("/recommend/reports")
async def list_recommendation_reports(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RecommendationReport)
        .where(RecommendationReport.user_id == user.id)
        .order_by(RecommendationReport.created_at.desc())
        .limit(20)
    )
    return {
        "reports": [
            {
                "id": str(report.id),
                "profile_version": report.profile_version,
                "is_stale": report.is_stale,
                "generated_at": report.created_at.isoformat() if report.created_at else None,
                "recommendation_count": len(report.recommendations or []),
            }
            for report in result.scalars().all()
        ]
    }


@router.get("/recommend/reports/{report_id}")
async def get_recommendation_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="推荐报告不存在") from exc
    result = await db.execute(
        select(RecommendationReport).where(
            RecommendationReport.id == report_uuid,
            RecommendationReport.user_id == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="推荐报告不存在")
    return {
        "id": str(report.id),
        "profile_version": report.profile_version,
        "is_stale": report.is_stale,
        "profile_snapshot": report.profile_snapshot or {},
        "recommendations": report.recommendations or [],
        "generated_at": report.created_at.isoformat() if report.created_at else None,
    }


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


def _saved_plan_dict(plan: LearningPlan) -> dict:
    return {
        "id": str(plan.id),
        "program": plan.program_name,
        "profile_version": plan.profile_version,
        "status": plan.status,
        "items": plan.items or [],
        "alternatives": plan.alternatives or [],
        "warnings": plan.warnings or [],
        "infeasible": plan.infeasible,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }


@router.post("/programs/plan")
async def save_course_plan(
    payload: SavePlanRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    profile = await _latest_profile(db, user.id) or {}
    db_plans = await _load_plans(db)
    plans = {**PROGRAM_PLANS, **db_plans}
    result = generate_plan(payload.program, profile, plans)
    if not result.items:
        raise HTTPException(status_code=404, detail=f"未找到「{payload.program}」的培养方案")

    if payload.adopt:
        await db.execute(
            update(LearningPlan)
            .where(LearningPlan.user_id == user.id, LearningPlan.status == "adopted")
            .values(status="archived", updated_at=utcnow())
        )
    plan = LearningPlan(
        user_id=user.id,
        program_name=result.program_name,
        profile_version=profile.get("version", 0),
        status="adopted" if payload.adopt else "draft",
        items=[_plan_item(item) for item in result.items],
        alternatives=[[_plan_item(item) for item in alt] for alt in result.alternatives],
        warnings=result.warnings,
        infeasible=result.infeasible,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return {"plan": _saved_plan_dict(plan)}


@router.get("/programs/plans")
async def list_saved_plans(
    include_archived: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(LearningPlan).where(LearningPlan.user_id == user.id)
    if not include_archived:
        query = query.where(LearningPlan.status != "archived")
    result = await db.execute(query.order_by(LearningPlan.updated_at.desc()).limit(20))
    return {"plans": [_saved_plan_dict(plan) for plan in result.scalars().all()]}


@router.get("/programs/plans/{plan_id}")
async def get_saved_plan(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningPlan).where(LearningPlan.id == plan_id, LearningPlan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="课程规划不存在")
    return {"plan": _saved_plan_dict(plan)}


@router.patch("/programs/plans/{plan_id}")
async def update_saved_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningPlan).where(LearningPlan.id == plan_id, LearningPlan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="课程规划不存在")
    plan.items = [item.model_dump() for item in payload.items]
    plan.status = "draft" if plan.status == "adopted" else plan.status
    plan.updated_at = utcnow()
    await db.commit()
    await db.refresh(plan)
    return {"plan": _saved_plan_dict(plan)}


@router.put("/programs/plans/{plan_id}/adopt")
async def adopt_saved_plan(
    plan_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LearningPlan).where(LearningPlan.id == plan_id, LearningPlan.user_id == user.id)
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="课程规划不存在")
    await db.execute(
        update(LearningPlan)
        .where(
            LearningPlan.user_id == user.id,
            LearningPlan.status == "adopted",
            LearningPlan.id != plan.id,
        )
        .values(status="archived", updated_at=utcnow())
    )
    plan.status = "adopted"
    plan.updated_at = utcnow()
    await db.commit()
    await db.refresh(plan)
    return {"plan": _saved_plan_dict(plan)}


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


def _job_application_dict(application: JobApplication) -> dict:
    return {
        "id": str(application.id),
        "job_id": application.job_id,
        "status": application.status,
        "channel": application.channel,
        "note": application.note,
        "applied_at": application.applied_at.isoformat() if application.applied_at else None,
        "updated_at": application.updated_at.isoformat() if application.updated_at else None,
    }


@router.get("/jobs/applications")
async def list_job_applications(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.user_id == user.id)
        .order_by(JobApplication.updated_at.desc())
    )
    return {"applications": [_job_application_dict(item) for item in result.scalars().all()]}


@router.put("/jobs/{job_id}/application")
async def upsert_job_application(
    job_id: str,
    payload: JobApplicationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在")
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.user_id == user.id,
            JobApplication.job_id == job_id,
        )
    )
    application = result.scalar_one_or_none()
    applied_at = payload.applied_at
    if payload.status == "applied" and applied_at is None:
        applied_at = utcnow()
    if application:
        application.status = payload.status
        application.channel = payload.channel.strip()
        application.note = payload.note.strip()
        application.applied_at = applied_at
        application.updated_at = utcnow()
    else:
        application = JobApplication(
            user_id=user.id,
            job_id=job_id,
            status=payload.status,
            channel=payload.channel.strip(),
            note=payload.note.strip(),
            applied_at=applied_at,
            updated_at=utcnow(),
        )
        db.add(application)
    await db.commit()
    await db.refresh(application)
    return {"application": _job_application_dict(application)}


@router.delete("/jobs/{job_id}/application")
async def delete_job_application(
    job_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobApplication).where(
            JobApplication.user_id == user.id,
            JobApplication.job_id == job_id,
        )
    )
    application = result.scalar_one_or_none()
    if not application:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    await db.delete(application)
    await db.commit()
    return {"status": "deleted", "job_id": job_id}


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
