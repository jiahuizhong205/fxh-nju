"""账号 API——注册、登录、鉴权依赖。

密码哈希用 stdlib PBKDF2（零外部依赖），token 用不透明随机串存库。
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import PasswordHistory, User, UserAccountLink, UserSession, utcnow

router = APIRouter()


# ── 密码哈希 / token 工具 ──────────────────────────────

def _hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return salt, digest


def _verify_password(password: str, salt: str, expected: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return hmac.compare_digest(digest, expected)


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_is_active(session: UserSession, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return session.revoked_at is None and bool(session.expires_at and session.expires_at > now)


def _new_session(user_id, token: str, request: Request | None = None) -> UserSession:
    return UserSession(
        user_id=user_id,
        token_hash=_hash_session_token(token),
        user_agent=(request.headers.get("user-agent", "") if request else "")[:500],
        ip_address=(request.client.host if request and request.client else "")[:64],
        expires_at=utcnow() + timedelta(days=30),
    )


async def _revoke_user_sessions(db: AsyncSession, user_id, now: datetime | None = None) -> None:
    now = now or utcnow()
    result = await db.execute(select(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.revoked_at.is_(None),
    ))
    for session in result.scalars().all():
        session.revoked_at = now


def _serialize_user(u: User) -> dict:
    return {
        "id": str(u.id),
        "username": u.username,
        "nickname": u.nickname,
        "onboarding_completed": bool(u.onboarding_completed),
    }


# ── 鉴权依赖 ──────────────────────────────────────────

async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.removeprefix("Bearer ").strip()
    result = await db.execute(select(User).where(User.token == token))
    user = result.scalar_one_or_none()
    if user:
        return user
    session_result = await db.execute(
        select(UserSession).where(UserSession.token_hash == _hash_session_token(token))
    )
    session = session_result.scalar_one_or_none()
    if not session or not _session_is_active(session):
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    session.last_seen_at = utcnow()
    session_user = await db.get(User, session.user_id)
    if not session_user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return session_user


# ── 请求体 ────────────────────────────────────────────

class _Credentials(BaseModel):
    username: str
    password: str
    nickname: str = ""


class _ChangePassword(BaseModel):
    old_password: str
    new_password: str


class _UpdateNickname(BaseModel):
    nickname: str


class _OnboardingUpdate(BaseModel):
    completed: bool


class AccountLinkRequest(BaseModel):
    username: str
    password: str


def _can_switch_account(current_user_id, target_user_id, linked_user_ids: set[str]) -> bool:
    return str(target_user_id) != str(current_user_id) and str(target_user_id) in linked_user_ids


def _validate_password(password: str) -> None:
    if not 8 <= len(password) <= 20:
        raise HTTPException(status_code=400, detail="密码长度须为 8-20 位")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=400, detail="密码须同时包含字母和数字")


# ── 端点 ──────────────────────────────────────────────

@router.post("/auth/register")
async def register(payload: _Credentials, request: Request, db: AsyncSession = Depends(get_db)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    _validate_password(payload.password)

    exists = await db.execute(select(User).where(User.username == username))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已被注册")

    salt, digest = _hash_password(payload.password)
    nickname = payload.nickname.strip() or username
    user = User(username=username, password_hash=digest, salt=salt, nickname=nickname)
    user.token = secrets.token_urlsafe(32)
    db.add(user)
    await db.flush()
    db.add(_new_session(user.id, user.token, request))
    await db.commit()
    await db.refresh(user)
    return {"token": user.token, "user": _serialize_user(user)}


@router.post("/auth/login")
async def login(payload: _Credentials, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username.strip()))
    user = result.scalar_one_or_none()
    if not user or not _verify_password(payload.password, user.salt, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.token = secrets.token_urlsafe(32)
    db.add(_new_session(user.id, user.token, request))
    await db.commit()
    await db.refresh(user)
    return {"token": user.token, "user": _serialize_user(user)}


@router.post("/auth/logout")
async def logout(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if token:
        result = await db.execute(select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.token_hash == _hash_session_token(token),
        ))
        session = result.scalar_one_or_none()
        if session:
            session.revoked_at = utcnow()
    user.token = None
    await db.commit()
    return {"status": "ok"}


@router.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": _serialize_user(user)}


@router.get("/auth/onboarding")
async def onboarding_status(user: User = Depends(get_current_user)):
    return {"onboarding_completed": bool(user.onboarding_completed)}


@router.put("/auth/onboarding")
async def update_onboarding(
    payload: _OnboardingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.onboarding_completed = payload.completed
    await db.commit()
    return {"onboarding_completed": user.onboarding_completed}


@router.post("/auth/change-password")
async def change_password(
    payload: _ChangePassword,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _verify_password(payload.old_password, user.salt, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    _validate_password(payload.new_password)
    history_result = await db.execute(
        select(PasswordHistory)
        .where(PasswordHistory.user_id == user.id)
        .order_by(PasswordHistory.created_at.desc())
        .limit(5)
    )
    previous_passwords = [user, *history_result.scalars().all()]
    if any(_verify_password(payload.new_password, item.salt, item.password_hash) for item in previous_passwords):
        raise HTTPException(status_code=400, detail="新密码不能复用最近使用过的密码")

    db.add(PasswordHistory(user_id=user.id, password_hash=user.password_hash, salt=user.salt))
    await _revoke_user_sessions(db, user.id)
    user.salt, user.password_hash = _hash_password(payload.new_password)
    # 改密后立即使旧 token 失效，避免旧会话继续访问账号数据。
    user.token = secrets.token_urlsafe(32)
    db.add(_new_session(user.id, user.token))
    await db.commit()
    return {"status": "ok", "token": user.token}


def _serialize_session(session: UserSession) -> dict:
    return {
        "id": str(session.id),
        "user_agent": session.user_agent,
        "ip_address": session.ip_address,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
        "expires_at": session.expires_at.isoformat() if session.expires_at else None,
        "revoked_at": session.revoked_at.isoformat() if session.revoked_at else None,
        "active": _session_is_active(session),
    }


@router.get("/auth/sessions")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.desc())
        .limit(20)
    )
    return {"sessions": [_serialize_session(session) for session in result.scalars().all()]}


@router.delete("/auth/sessions/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserSession).where(
        UserSession.id == session_id,
        UserSession.user_id == user.id,
    ))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    session.revoked_at = utcnow()
    await db.commit()
    return {"status": "revoked", "session_id": str(session.id)}


def _serialize_account(user: User, current: bool = False) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "nickname": user.nickname,
        "onboarding_completed": bool(user.onboarding_completed),
        "current": current,
    }


@router.get("/auth/accounts")
async def list_linked_accounts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(UserAccountLink)
        .where(UserAccountLink.owner_user_id == user.id)
        .order_by(UserAccountLink.created_at.desc())
    )
    accounts = [_serialize_account(user, current=True)]
    for link in result.scalars().all():
        linked = await db.get(User, link.linked_user_id)
        if linked:
            accounts.append(_serialize_account(linked))
    return {"accounts": accounts}


@router.post("/auth/accounts/link")
async def link_account(
    payload: AccountLinkRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == payload.username.strip()))
    target = result.scalar_one_or_none()
    if not target or not _verify_password(payload.password, target.salt, target.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if target.id == user.id:
        raise HTTPException(status_code=400, detail="不能关联当前账号")

    existing = await db.execute(select(UserAccountLink).where(
        UserAccountLink.owner_user_id == user.id,
        UserAccountLink.linked_user_id == target.id,
    ))
    if not existing.scalar_one_or_none():
        db.add(UserAccountLink(owner_user_id=user.id, linked_user_id=target.id))
    reverse = await db.execute(select(UserAccountLink).where(
        UserAccountLink.owner_user_id == target.id,
        UserAccountLink.linked_user_id == user.id,
    ))
    if not reverse.scalar_one_or_none():
        db.add(UserAccountLink(owner_user_id=target.id, linked_user_id=user.id))
    await db.commit()
    return {"status": "linked", "account": _serialize_account(target)}


@router.post("/auth/accounts/{account_id}/switch")
async def switch_account(
    account_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserAccountLink).where(
        UserAccountLink.owner_user_id == user.id,
        UserAccountLink.linked_user_id == account_id,
    ))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="该账号未关联，不能切换")
    target = await db.get(User, account_id)
    if not target:
        raise HTTPException(status_code=404, detail="账号不存在")
    target.token = secrets.token_urlsafe(32)
    db.add(_new_session(target.id, target.token, request))
    await db.commit()
    return {"status": "switched", "token": target.token, "user": _serialize_user(target)}


@router.delete("/auth/accounts/{account_id}")
async def unlink_account(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserAccountLink).where(
        UserAccountLink.owner_user_id == user.id,
        UserAccountLink.linked_user_id == account_id,
    ))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="账号关联不存在")
    await db.delete(link)
    reverse_result = await db.execute(select(UserAccountLink).where(
        UserAccountLink.owner_user_id == account_id,
        UserAccountLink.linked_user_id == user.id,
    ))
    reverse = reverse_result.scalar_one_or_none()
    if reverse:
        await db.delete(reverse)
    await db.commit()
    return {"status": "unlinked", "account_id": str(account_id)}


@router.post("/auth/nickname")
async def update_nickname(
    payload: _UpdateNickname,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    nickname = payload.nickname.strip()
    if not nickname:
        raise HTTPException(status_code=400, detail="昵称不能为空")
    if len(nickname) > 50:
        raise HTTPException(status_code=400, detail="昵称最多 50 字")
    user.nickname = nickname
    await db.commit()
    return {"user": _serialize_user(user)}
