"""统一加载推荐与规划所需的最新学生画像。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.models import LearningRecord, StudentProfile


async def load_student_profile_context(
    db: AsyncSession,
    user_id,
) -> dict | None:
    profile_result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user_id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        return None

    records_result = await db.execute(
        select(LearningRecord).where(
            LearningRecord.user_id == user_id,
            LearningRecord.status == "completed",
        )
    )
    completed_records = records_result.scalars().all()
    return {
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
        "completed_courses": [record.course_name for record in completed_records],
        "completed_credits": sum(record.credits for record in completed_records),
    }
