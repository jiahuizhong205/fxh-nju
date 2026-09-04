"""用户意见反馈 API。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
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
    )
    db.add(feedback)
    await db.commit()
    return {"id": str(feedback.id), "status": "received"}
