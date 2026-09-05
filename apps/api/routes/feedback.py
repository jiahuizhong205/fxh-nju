"""用户意见反馈 API。"""

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import Feedback, FeedbackAttachment, FeedbackReply, User, utcnow
from apps.api.routes.auth import get_current_user
from apps.api.routes.notifications import enqueue_preference_notification

router = APIRouter()

ATTACHMENT_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024
ATTACHMENT_SIGNATURES = {
    "image/jpeg": lambda content: content.startswith(b"\xff\xd8\xff"),
    "image/png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda content: content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    "image/gif": lambda content: content.startswith((b"GIF87a", b"GIF89a")),
    "application/pdf": lambda content: content.startswith(b"%PDF-"),
}


class FeedbackCreate(BaseModel):
    feedback_type: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1, max_length=5000)
    contact: str = Field(default="", max_length=200)
    attachments: list[str] = Field(default_factory=list, max_length=3)


class FeedbackAdminUpdate(BaseModel):
    status: Literal["received", "in_progress", "resolved"]


class FeedbackAdminReply(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("回复内容不能为空")
        return value


def _require_admin(user: User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")


def _mask_feedback_contact(value: str) -> str:
    """管理端只展示可用于人工识别的最小联系方式片段。"""
    value = (value or "").strip()
    if not value:
        return ""
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}*****@{domain}"
    if len(value) >= 7:
        return f"{value[:3]}****{value[-4:]}"
    return "***"


def _validate_attachment(content_type: str | None, content: bytes) -> None:
    if content_type not in ATTACHMENT_CONTENT_TYPES:
        raise ValueError("附件仅支持 JPG、PNG、WebP、GIF 或 PDF")
    if not content:
        raise ValueError("附件文件不能为空")
    if len(content) > ATTACHMENT_MAX_BYTES:
        raise ValueError("单个附件不能超过 5 MB")
    signature_check = ATTACHMENT_SIGNATURES[content_type]
    if not signature_check(content):
        raise ValueError("附件内容与声明的文件类型不匹配")


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


def _serialize_feedback(
    feedback: Feedback,
    *,
    mask_contact: bool = False,
    replies: list[FeedbackReply] | None = None,
) -> dict:
    return {
        "id": str(feedback.id),
        "feedback_type": feedback.feedback_type,
        "content": feedback.content,
        "contact": _mask_feedback_contact(feedback.contact) if mask_contact else feedback.contact,
        "attachments": feedback.attachments or [],
        "replies": [_serialize_reply(item) for item in (replies or [])],
        "status": feedback.status,
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        "updated_at": feedback.updated_at.isoformat() if feedback.updated_at else None,
    }


def _serialize_reply(reply: FeedbackReply) -> dict:
    return {
        "id": str(reply.id),
        "content": reply.content,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
    }


async def _load_replies(db: AsyncSession, feedback_ids: list[UUID]) -> dict[UUID, list[FeedbackReply]]:
    if not feedback_ids:
        return {}
    result = await db.execute(
        select(FeedbackReply)
        .where(FeedbackReply.feedback_id.in_(feedback_ids))
        .order_by(FeedbackReply.created_at)
    )
    grouped: dict[UUID, list[FeedbackReply]] = {}
    for reply in result.scalars().all():
        grouped.setdefault(reply.feedback_id, []).append(reply)
    return grouped


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
    items = result.scalars().all()
    replies = await _load_replies(db, [item.id for item in items])
    return {
        "feedback": [
            _serialize_feedback(item, replies=replies.get(item.id, []))
            for item in items
        ]
    }


@router.get("/admin/feedback")
async def admin_list_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    result = await db.execute(
        select(Feedback).order_by(Feedback.updated_at.desc()).limit(limit)
    )
    return {
        "feedback": [
            {**_serialize_feedback(item, mask_contact=True), "user_id": str(item.user_id)}
            for item in result.scalars().all()
        ]
    }


@router.patch("/admin/feedback/{feedback_id}")
async def admin_update_feedback(
    feedback_id: UUID,
    payload: FeedbackAdminUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    feedback.status = payload.status
    feedback.updated_at = utcnow()
    await db.commit()
    await db.refresh(feedback)
    return {"feedback": _serialize_feedback(feedback)}


@router.post("/admin/feedback/{feedback_id}/replies")
async def admin_reply_feedback(
    feedback_id: UUID,
    payload: FeedbackAdminReply,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_admin(user)
    feedback_result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = feedback_result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    reply = FeedbackReply(
        feedback_id=feedback.id,
        admin_user_id=user.id,
        content=payload.content,
    )
    db.add(reply)
    feedback.updated_at = utcnow()
    target_result = await db.execute(select(User).where(User.id == feedback.user_id))
    target_user = target_result.scalar_one_or_none()
    if target_user:
        await enqueue_preference_notification(
            db,
            target_user,
            "意见反馈回复",
            "feedback_reply",
            "你的反馈有新回复",
            payload.content,
        )
    await db.commit()
    await db.refresh(reply)
    return {"reply": _serialize_reply(reply)}


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
    replies = await _load_replies(db, [feedback.id])
    return {"feedback": _serialize_feedback(feedback, replies=replies.get(feedback.id, []))}


@router.post("/feedback/{feedback_id}/attachments")
async def upload_feedback_attachments(
    feedback_id: UUID,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feedback_result = await db.execute(select(Feedback).where(
        Feedback.id == feedback_id,
        Feedback.user_id == user.id,
    ))
    feedback = feedback_result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    existing = await db.execute(select(FeedbackAttachment).where(
        FeedbackAttachment.feedback_id == feedback.id,
    ))
    existing_attachments = existing.scalars().all()
    if len(existing_attachments) + len(files) > 3:
        raise HTTPException(status_code=400, detail="每条反馈最多上传 3 个附件")

    saved = []
    for file in files:
        content = await file.read()
        try:
            _validate_attachment(file.content_type, content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        attachment = FeedbackAttachment(
            feedback_id=feedback.id,
            filename=(file.filename or "attachment")[:255],
            content_type=file.content_type,
            data=content,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        db.add(attachment)
        saved.append(attachment)
        feedback.attachments = [
            *(feedback.attachments or []),
            {"id": str(attachment.id), "filename": attachment.filename},
        ]
    feedback.updated_at = utcnow()
    await db.commit()
    return {
        "attachments": [{
            "id": str(item.id),
            "filename": item.filename,
            "content_type": item.content_type,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256,
        } for item in saved]
    }


@router.get("/feedback/{feedback_id}/attachments/{attachment_id}")
async def download_feedback_attachment(
    feedback_id: UUID,
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    feedback_result = await db.execute(select(Feedback).where(
        Feedback.id == feedback_id,
        Feedback.user_id == user.id,
    ))
    if not feedback_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="反馈不存在")
    attachment = await db.get(FeedbackAttachment, attachment_id)
    if not attachment or attachment.feedback_id != feedback_id:
        raise HTTPException(status_code=404, detail="附件不存在")
    return Response(
        content=attachment.data,
        media_type=attachment.content_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.filename}"'},
    )
