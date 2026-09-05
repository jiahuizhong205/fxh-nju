"""账号 API——注册、登录、鉴权依赖。

密码哈希用 stdlib PBKDF2（零外部依赖），token 用不透明随机串存库。
"""

import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import User

router = APIRouter()


# ── 密码哈希 / token 工具 ──────────────────────────────

def _hash_password(password: str) -> tuple[str, str]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return salt, digest


def _verify_password(password: str, salt: str, expected: str) -> bool:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return hmac.compare_digest(digest, expected)


def _serialize_user(u: User) -> dict:
    return {"id": str(u.id), "username": u.username, "nickname": u.nickname}


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
    if not user:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return user


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


def _validate_password(password: str) -> None:
    if not 8 <= len(password) <= 20:
        raise HTTPException(status_code=400, detail="密码长度须为 8-20 位")
    if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
        raise HTTPException(status_code=400, detail="密码须同时包含字母和数字")


# ── 端点 ──────────────────────────────────────────────

@router.post("/auth/register")
async def register(payload: _Credentials, db: AsyncSession = Depends(get_db)):
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
    await db.commit()
    await db.refresh(user)
    return {"token": user.token, "user": _serialize_user(user)}


@router.post("/auth/login")
async def login(payload: _Credentials, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == payload.username.strip()))
    user = result.scalar_one_or_none()
    if not user or not _verify_password(payload.password, user.salt, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user.token = secrets.token_urlsafe(32)
    await db.commit()
    await db.refresh(user)
    return {"token": user.token, "user": _serialize_user(user)}


@router.post("/auth/logout")
async def logout(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user.token = None
    await db.commit()
    return {"status": "ok"}


@router.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {"user": _serialize_user(user)}


@router.post("/auth/change-password")
async def change_password(
    payload: _ChangePassword,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _verify_password(payload.old_password, user.salt, user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码错误")
    _validate_password(payload.new_password)

    user.salt, user.password_hash = _hash_password(payload.new_password)
    # 改密后立即使旧 token 失效，避免旧会话继续访问账号数据。
    user.token = secrets.token_urlsafe(32)
    await db.commit()
    return {"status": "ok", "token": user.token}


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
