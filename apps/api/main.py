"""福小禾 API——FastAPI 入口。"""

import logging
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.database import async_session, init_db
from apps.api.routes import account, auth, cache, chat, feedback, knowledge, meta, notifications, preferences, profile, planning, sync
from apps.api.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    TraceMiddleware,
    RequestLogMiddleware,
)

# 结构化日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("fuxiaohe")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("fuxiaohe starting...")
    await init_db()
    yield
    logger.info("fuxiaohe shutting down...")


app = FastAPI(
    title="福小禾 API",
    description="南大复合型人才学习助手",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Trace-Id"],
)

# 安全中间件（后加的先执行——Starlette 洋葱模型）
app.add_middleware(RequestLogMiddleware)
app.add_middleware(TraceMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(account.router, prefix="/api/v1", tags=["account"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
app.include_router(profile.router, prefix="/api/v1", tags=["profile"])
app.include_router(preferences.router, prefix="/api/v1", tags=["preferences"])
app.include_router(feedback.router, prefix="/api/v1", tags=["feedback"])
app.include_router(planning.router, prefix="/api/v1", tags=["planning"])
app.include_router(sync.router, prefix="/api/v1", tags=["sync"])
app.include_router(notifications.router, prefix="/api/v1", tags=["notifications"])
app.include_router(cache.router, prefix="/api/v1", tags=["cache"])
app.include_router(meta.router, prefix="/api/v1", tags=["meta"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
