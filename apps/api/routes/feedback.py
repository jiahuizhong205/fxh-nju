"""用户意见反馈 API。"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import Feedback, User
from apps.api.routes.auth import get_current_user

router = APIRouter()


class FeedbackCreate(BaseModel):
    feedback_type: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=5000)
    contact: str = Field(default="", max_length=200)
    attachments: list[str] = Field(default_factory=list, max_length=3)


@router.post("/feedback")
async def create_feedback(
    payload: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if len(payload.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="反馈内容不能为空")
    feedback = Feedback(
        user_id=user.id,
        feedback_type=payload.feedback_type,
        content=payload.content.strip(),
        contact=payload.contact.strip(),
        attachments=payload.attachments,
        status="received",
    )
    db.add(feedback)
    await db.commit()
    return {"id": str(feedback.id), "status": feedback.status}


def _serialize_feedback(feedback: Feedback) -> dict:
    return {
        "id": str(feedback.id),
        "feedback_type": feedback.feedback_type,
        "content": feedback.content,
        "contact": feedback.contact,
        "attachments": feedback.attachments or [],
        "status": feedback.status,
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        "updated_at": feedback.updated_at.isoformat() if feedback.updated_at else None,
    }


@router.get("/feedback")
async def list_feedback(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback)
        .where(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc())
    )
    return {"feedback": [_serialize_feedback(item) for item in result.scalars().all()]}


@router.get("/feedback/{feedback_id}")
async def get_feedback(
    feedback_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Feedback).where(Feedback.id == feedback_id, Feedback.user_id == user.id)
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    return {"feedback": _serialize_feedback(feedback)}
