"""福小禾 API——FastAPI 入口。"""

import logging
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.database import async_session, get_db, init_db
from apps.api.models import Document, DocumentChunk
from apps.api.routes import account, auth, cache, chat, feedback, friends, knowledge, meta, notifications, preferences, profile, planning, sync
from apps.api.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    TraceMiddleware,
    RequestLogMiddleware,
)
from services.rag.retrieval import embedding_signature

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
app.include_router(friends.router, prefix="/api/v1", tags=["friends"])
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


@app.get("/api/readiness")
async def readiness(db: AsyncSession = Depends(get_db)):
    """检查主流程所需数据和外部模型配置，不暴露任何凭据。"""
    try:
        document_count = int((await db.execute(
            select(func.count(Document.id)).where(Document.is_active.is_(True))
        )).scalar_one())
        metadata_rows = (await db.execute(select(DocumentChunk.metadata_))).scalars().all()
        chunk_count = len(metadata_rows)
    except Exception:
        logger.exception("readiness database check failed")
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "error"})

    llm_configured = all((settings.llm_base_url, settings.llm_model, settings.llm_api_key))
    embedding_configured = all((settings.embedding_base_url, settings.embedding_api_model, settings.embedding_api_key))
    expected_signature = embedding_signature()
    indexed_for_provider = sum(
        1 for metadata in metadata_rows
        if (metadata or {}).get("embedding_signature") == expected_signature
    )
    knowledge_ready = document_count > 0 and chunk_count > 0
    provider_ready = settings.mock_llm or (
        llm_configured and embedding_configured and indexed_for_provider == chunk_count
    )
    ready = knowledge_ready and provider_ready
    payload = {
        "status": "ready" if ready else "not_ready",
        "database": "ok",
        "knowledge": {
            "active_documents": document_count,
            "chunks": chunk_count,
            "indexed_for_current_provider": indexed_for_provider,
        },
        "llm": {"mode": "mock" if settings.mock_llm else "external", "configured": llm_configured},
        "embedding": {
            "mode": "mock-hash" if settings.mock_llm else "external",
            "configured": embedding_configured,
            "expected_dimension": settings.embedding_dimension,
        },
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)
