"""好友关系 API，并为公开画像提供服务端好友判定。"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import User, UserFriendship, utcnow
from apps.api.routes.auth import get_current_user
from packages.contracts.schemas import FriendRequest

router = APIRouter()


def _serialize(friendship: UserFriendship, *, viewer_id: uuid.UUID, other: User | None) -> dict:
    is_outgoing = friendship.requester_id == viewer_id
    other_id = friendship.addressee_id if is_outgoing else friendship.requester_id
    return {
        "id": str(friendship.id),
        "user_id": str(other.id) if other else str(other_id),
        "username": other.username if other else "",
        "nickname": other.nickname if other else "",
        "direction": "outgoing" if is_outgoing else "incoming",
        "status": friendship.status,
        "created_at": friendship.created_at.isoformat() if friendship.created_at else None,
        "updated_at": friendship.updated_at.isoformat() if friendship.updated_at else None,
        "accepted_at": friendship.accepted_at.isoformat() if friendship.accepted_at else None,
    }


async def are_friends(db: AsyncSession, viewer_id: uuid.UUID, target_id: uuid.UUID) -> bool:
    """仅 accepted 关系可满足“仅好友”可见范围。"""
    if viewer_id == target_id:
        return True
    result = await db.execute(
        select(UserFriendship.id).where(
            UserFriendship.status == "accepted",
            or_(
                (UserFriendship.requester_id == viewer_id) & (UserFriendship.addressee_id == target_id),
                (UserFriendship.requester_id == target_id) & (UserFriendship.addressee_id == viewer_id),
            ),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None


@router.get("/friends")
async def list_friends(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserFriendship)
        .where(or_(UserFriendship.requester_id == user.id, UserFriendship.addressee_id == user.id))
        .order_by(UserFriendship.updated_at.desc())
    )
    relationships = result.scalars().all()
    other_ids = {
        relationship.addressee_id if relationship.requester_id == user.id else relationship.requester_id
        for relationship in relationships
    }
    users = {}
    if other_ids:
        users = {item.id: item for item in (await db.execute(select(User).where(User.id.in_(other_ids)))).scalars().all()}
    return {
        "friends": [
            _serialize(
                relationship,
                viewer_id=user.id,
                other=users.get(
                    relationship.addressee_id if relationship.requester_id == user.id else relationship.requester_id
                ),
            )
            for relationship in relationships
        ]
    }


@router.post("/friends/requests")
async def send_friend_request(
    payload: FriendRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.user_id == user.id:
        raise HTTPException(status_code=400, detail="不能添加自己为好友")
    target = await db.get(User, payload.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="目标用户不存在")

    existing_result = await db.execute(
        select(UserFriendship).where(or_(
            (UserFriendship.requester_id == user.id) & (UserFriendship.addressee_id == target.id),
            (UserFriendship.requester_id == target.id) & (UserFriendship.addressee_id == user.id),
        )).limit(1)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        if existing.status == "accepted":
            raise HTTPException(status_code=409, detail="你们已经是好友")
        raise HTTPException(status_code=409, detail="已有待处理的好友请求")

    friendship = UserFriendship(
        requester_id=user.id,
        addressee_id=target.id,
        status="pending",
        updated_at=utcnow(),
    )
    db.add(friendship)
    await db.commit()
    await db.refresh(friendship)
    return {"friendship": _serialize(friendship, viewer_id=user.id, other=target)}


@router.post("/friends/{friendship_id}/accept")
async def accept_friend_request(
    friendship_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    friendship = await db.get(UserFriendship, friendship_id)
    if not friendship:
        raise HTTPException(status_code=404, detail="好友请求不存在")
    if friendship.addressee_id != user.id:
        raise HTTPException(status_code=403, detail="只有接收方可以接受好友请求")
    if friendship.status != "pending":
        raise HTTPException(status_code=409, detail="好友请求已处理")
    friendship.status = "accepted"
    friendship.accepted_at = utcnow()
    friendship.updated_at = utcnow()
    await db.commit()
    target = await db.get(User, friendship.requester_id)
    return {"friendship": _serialize(friendship, viewer_id=user.id, other=target)}


@router.delete("/friends/{friendship_id}")
async def remove_friend(
    friendship_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    friendship = await db.get(UserFriendship, friendship_id)
    if not friendship:
        raise HTTPException(status_code=404, detail="好友关系不存在")
    if user.id not in (friendship.requester_id, friendship.addressee_id):
        raise HTTPException(status_code=403, detail="无权操作该好友关系")
    await db.delete(friendship)
    await db.commit()
    return {"status": "deleted"}
