"""学生画像 API——CRUD 用户画像。"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import LearningRecord, RecommendationReport, StudentProfile, User, UserAvatar, utcnow
from apps.api.config import settings
from apps.api.routes.auth import get_current_user
from apps.api.routes.preferences import VisibilityPreferences

router = APIRouter()

PROFILE_OPTIONS_VERSION = 1
INTEREST_OPTIONS = (
    "数据分析", "写作创作", "商业策划", "人文哲思", "硬核科技", "设计艺术",
    "写作", "传播", "编程", "设计", "法律", "金融", "人工智能",
)
STRENGTH_OPTIONS = (
    "逻辑推理", "沟通表达", "创意思维", "数据处理", "动手实验", "组织协调",
    "外语能力", "编程基础", "表达沟通", "其他",
)


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

    @field_validator("interests")
    @classmethod
    def validate_interests(cls, values: list[str]) -> list[str]:
        invalid = sorted(set(values) - set(INTEREST_OPTIONS))
        if invalid:
            raise ValueError(f"兴趣选项不合法: {', '.join(invalid)}")
        return list(dict.fromkeys(values))

    @field_validator("strengths")
    @classmethod
    def validate_strengths(cls, values: list[str]) -> list[str]:
        invalid = sorted(set(values) - set(STRENGTH_OPTIONS))
        if invalid:
            raise ValueError(f"能力选项不合法: {', '.join(invalid)}")
        return list(dict.fromkeys(values))


AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
AVATAR_MAX_BYTES = 2 * 1024 * 1024


def _validate_avatar(content_type: str | None, content: bytes) -> None:
    if content_type not in AVATAR_CONTENT_TYPES:
        raise ValueError("头像仅支持 JPG、PNG 或 WebP")
    if not content:
        raise ValueError("头像文件不能为空")
    if len(content) > min(AVATAR_MAX_BYTES, settings.max_upload_bytes):
        raise ValueError("头像文件不能超过 2 MB")


@router.get("/profile/options")
def get_profile_options():
    return {
        "version": PROFILE_OPTIONS_VERSION,
        "interests": list(INTEREST_OPTIONS),
        "strengths": list(STRENGTH_OPTIONS),
    }


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


@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    try:
        _validate_avatar(file.content_type, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = await db.execute(select(UserAvatar).where(UserAvatar.user_id == user.id))
    avatar = result.scalar_one_or_none()
    if avatar:
        avatar.content_type = file.content_type
        avatar.data = content
        avatar.size_bytes = len(content)
        avatar.updated_at = utcnow()
    else:
        avatar = UserAvatar(
            user_id=user.id,
            content_type=file.content_type,
            data=content,
            size_bytes=len(content),
            updated_at=utcnow(),
        )
        db.add(avatar)
    await db.commit()
    await db.refresh(avatar)
    return {
        "avatar": {
            "size_bytes": avatar.size_bytes,
            "content_type": avatar.content_type,
            "updated_at": avatar.updated_at.isoformat() if avatar.updated_at else None,
        }
    }


@router.get("/profile/avatar")
async def get_avatar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from fastapi.responses import Response

    result = await db.execute(select(UserAvatar).where(UserAvatar.user_id == user.id))
    avatar = result.scalar_one_or_none()
    if not avatar:
        raise HTTPException(status_code=404, detail="尚未设置头像")
    return Response(content=avatar.data, media_type=avatar.content_type)


@router.delete("/profile/avatar")
async def delete_avatar(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserAvatar).where(UserAvatar.user_id == user.id))
    avatar = result.scalar_one_or_none()
    if not avatar:
        raise HTTPException(status_code=404, detail="尚未设置头像")
    await db.delete(avatar)
    await db.commit()
    return {"status": "deleted"}


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


def _can_view_profile(scope: str, *, is_self: bool, same_major: bool) -> bool:
    """统一执行可见范围；好友关系尚未建立时不把普通用户误判为好友。"""
    if is_self:
        return True
    return {
        "全校公开": True,
        "同专业同学": same_major,
        "仅好友": False,
        "仅自己": False,
    }.get(scope, False)


def _public_profile_summary(
    user: User,
    profile: StudentProfile,
    visibility: VisibilityPreferences,
    records: list[LearningRecord],
) -> dict:
    summary = {"user_id": str(user.id), "nickname": user.nickname}
    if visibility.show_grade:
        summary["grade"] = profile.grade
    if visibility.show_course:
        completed = [record for record in records if record.status == "completed"]
        summary["completed_course_count"] = len(completed)
        summary["completed_credits"] = sum(record.credits for record in completed)
    if visibility.show_timetable:
        summary["timetable_preferences"] = profile.schedule_preferences or {}
    return summary


@router.get("/profiles/{user_id}/public-summary")
async def public_profile_summary(
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_user = await db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    target_result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user_id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    target_profile = target_result.scalar_one_or_none()
    if not target_profile:
        raise HTTPException(status_code=404, detail="该用户尚未建立画像")

    viewer_result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.user_id == user.id)
        .order_by(StudentProfile.updated_at.desc())
        .limit(1)
    )
    viewer_profile = viewer_result.scalar_one_or_none()
    visibility = VisibilityPreferences.model_validate((target_user.preferences or {}).get("visibility", {}))
    if not _can_view_profile(
        visibility.scope,
        is_self=user.id == user_id,
        same_major=bool(viewer_profile and viewer_profile.major == target_profile.major),
    ):
        raise HTTPException(status_code=403, detail="该用户未向你开放此画像范围")

    records_result = await db.execute(
        select(LearningRecord).where(LearningRecord.user_id == user_id)
    )
    return {"profile": _public_profile_summary(target_user, target_profile, visibility, records_result.scalars().all())}
