"""账号级站内通知 API。"""

import uuid

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import Notification, User, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()


class NotificationReadRequest(BaseModel):
    read: StrictBool = True


def _serialize(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "category": notification.category,
        "title": notification.title,
        "body": notification.body,
        "channel": notification.channel,
        "status": notification.status,
        "scheduled_at": notification.scheduled_at.isoformat() if notification.scheduled_at else None,
        "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "retry_count": notification.retry_count,
        "last_error": notification.last_error,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }


async def enqueue_notification(
    db: AsyncSession,
    user_id,
    category: str,
    title: str,
    body: str,
    channel: str = "in_app",
) -> Notification:
    notification = Notification(
        user_id=user_id,
        category=category,
        title=title,
        body=body,
        channel=channel,
        status="queued",
        scheduled_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(notification)
    return notification


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    result = await db.execute(
        query.order_by(Notification.created_at.desc()).limit(limit)
    )
    unread = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
    )
    return {
        "notifications": [_serialize(item) for item in result.scalars().all()],
        "unread_count": int(unread.scalar_one()),
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    payload: NotificationReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")
    notification.read_at = utcnow() if payload.read else None
    if payload.read:
        notification.status = "read"
    elif notification.status == "read":
        notification.status = "sent"
    notification.updated_at = utcnow()
    await db.commit()
    await db.refresh(notification)
    return {"notification": _serialize(notification)}
