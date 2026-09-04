"""账号级偏好设置 API。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import User
from apps.api.routes.auth import get_current_user

router = APIRouter()


class PreferencesUpdate(BaseModel):
    preferences: dict = Field(default_factory=dict)


@router.get("/preferences")
async def get_preferences(user: User = Depends(get_current_user)):
    return {"preferences": user.preferences or {}}


@router.put("/preferences")
async def update_preferences(
    payload: PreferencesUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.preferences = payload.preferences
    await db.commit()
    return {"preferences": user.preferences}
