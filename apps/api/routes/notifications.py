"""账号级站内通知 API。"""

import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import Notification, User, utcnow
from apps.api.routes.auth import get_current_user

router = APIRouter()

DEFAULT_NOTIFICATION_PREFERENCES = {
    "学习浇水提醒": True,
    "新岗位开花推送": True,
    "政策藤蔓更新": True,
    "推荐报告完成": False,
    "课表冲突预警": True,
}
MAX_EXTERNAL_NOTIFICATION_RETRIES = 3


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


def _deliver_in_app(notification: Notification, now: datetime | None = None) -> bool:
    """推进到期的站内通知；外部渠道不在这里伪造投递成功。"""
    now = now or utcnow()
    if notification.channel != "in_app" or notification.status != "queued":
        return False
    if notification.scheduled_at and notification.scheduled_at > now:
        return False
    notification.status = "sent"
    notification.sent_at = now
    notification.updated_at = now
    return True


def _deliver_external(notification: Notification, sender, now: datetime | None = None) -> bool:
    """调用注入的外部供应商；失败按指数退避，超过上限进入 failed。"""
    now = now or utcnow()
    if notification.channel == "in_app" or notification.status != "queued":
        return False
    if notification.scheduled_at and notification.scheduled_at > now:
        return False
    try:
        sender(notification)
    except Exception as exc:  # provider boundary: persist failure, never leak it to the user
        notification.retry_count = (notification.retry_count or 0) + 1
        notification.last_error = str(exc)[:2000]
        if notification.retry_count >= MAX_EXTERNAL_NOTIFICATION_RETRIES:
            notification.status = "failed"
        else:
            notification.scheduled_at = now + timedelta(minutes=2 ** (notification.retry_count - 1))
        notification.updated_at = now
        return False
    notification.status = "sent"
    notification.sent_at = now
    notification.last_error = ""
    notification.updated_at = now
    return True


def _notification_enabled(user: User, key: str) -> bool:
    """按通知设置页的默认值判断某个事件是否允许入队。"""
    configured = (user.preferences or {}).get("notifications", {})
    if key in configured:
        return bool(configured[key])
    return DEFAULT_NOTIFICATION_PREFERENCES.get(key, True)


def _learning_reminder_due(user: User, now: datetime | None = None) -> bool:
    """判断当前分钟是否应该生成学习提醒。"""
    now = now or utcnow()
    preferences = (user.preferences or {}).get("learning_reminder", {})
    if preferences.get("enabled", True) is not True:
        return False
    if preferences.get("time", "09:00") != now.strftime("%H:%M"):
        return False

    frequency = preferences.get("frequency", "每日浇水")
    week_days = preferences.get("week_days", []) or []
    if frequency == "仅工作日" and now.weekday() >= 5:
        return False
    if frequency == "隔日浇水" and now.date().toordinal() % 2:
        return False
    if frequency == "每周浇水":
        return now.weekday() in (week_days or [0])
    if frequency == "自定义":
        return now.weekday() in week_days
    return True


async def enqueue_due_learning_reminder(
    db: AsyncSession,
    user: User,
    now: datetime | None = None,
) -> Notification | None:
    """在通知列表被拉取时补入当天到期的学习提醒，并按自然日去重。"""
    now = now or utcnow()
    if not _learning_reminder_due(user, now):
        return None
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.category == "learning_reminder",
            Notification.created_at >= day_start,
        )
        .order_by(Notification.created_at.desc())
        .limit(1)
    )
    if result.scalar_one_or_none():
        return None
    return await enqueue_preference_notification(
        db,
        user,
        "学习浇水提醒",
        "learning_reminder",
        "该给学习计划浇水了",
        "打开你的课程规划，完成今天的一小步学习任务吧。",
    )


async def _deliver_due_in_app(db: AsyncSession, user_id, limit: int = 100) -> int:
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.channel == "in_app",
            Notification.status == "queued",
        )
        .order_by(Notification.created_at)
        .limit(limit)
    )
    delivered = sum(1 for item in result.scalars().all() if _deliver_in_app(item))
    if delivered:
        await db.commit()
    return delivered


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


async def enqueue_preference_notification(
    db: AsyncSession,
    user: User,
    preference_key: str,
    category: str,
    title: str,
    body: str,
    channel: str = "in_app",
) -> Notification | None:
    """仅在用户开启对应开关时创建通知，避免事件触发绕过偏好设置。"""
    if not _notification_enabled(user, preference_key):
        return None
    return await enqueue_notification(db, user.id, category, title, body, channel)


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enqueue_due_learning_reminder(db, user)
    await _deliver_due_in_app(db, user.id)
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
