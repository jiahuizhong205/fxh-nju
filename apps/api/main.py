"""福小禾 API——FastAPI 入口。"""

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.database import async_session, init_db
from apps.api.routes import chat, knowledge, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="福小禾 API",
    description="南大复合型人才学习助手",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
app.include_router(profile.router, prefix="/api/v1", tags=["profile"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
