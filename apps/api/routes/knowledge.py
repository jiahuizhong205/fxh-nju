"""知识库管理 API——文档上传、摄取与版本治理。"""

import io
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from apps.api.models import Document, User
from apps.api.config import settings
from apps.api.routes.auth import get_current_user
from services.rag.ingestion import ingest_document
from services.rag.retrieval import hybrid_search, build_citations

router = APIRouter()

VALID_TRUST_LEVELS = {"S", "A", "B", "C"}
VALID_SOURCE_TYPES = {"policy", "regulation", "course_catalog", "job_posting", "other"}
VALID_CONTENT_TYPES = {"text/plain", "text/markdown", "application/pdf"}


def _extract_upload_text(content: bytes, content_type: str | None, filename: str | None) -> str:
    is_pdf = content_type == "application/pdf" or (filename or "").lower().endswith(".pdf")
    if is_pdf:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"PDF 解析失败: {exc}") from exc
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF 未提取到可检索文字，可能是扫描件")
        return text
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="文本文件必须使用 UTF-8 编码") from exc


@router.post("/knowledge/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    trust_level: str = Form("A"),
    source_type: str = Form("policy"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if trust_level not in VALID_TRUST_LEVELS:
        raise HTTPException(status_code=400, detail=f"trust_level 须为 {VALID_TRUST_LEVELS} 之一")
    if source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"source_type 须为 {VALID_SOURCE_TYPES} 之一")

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail=f"文件超过 {settings.max_upload_bytes // 1024 // 1024} MB 限制")
    if file.content_type and file.content_type not in VALID_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")

    text = _extract_upload_text(content, file.content_type, file.filename)
    try:
        doc = await ingest_document(
            db, title=title, content=text,
            trust_level=trust_level, source_type=source_type,
        )
        return {"document_id": str(doc.id), "title": doc.title, "trust_level": doc.trust_level}
    except ValueError as e:
        return {"error": str(e), "status": "duplicate"}


@router.post("/knowledge/documents/text")
async def ingest_text(
    title: str = Form(...),
    content: str = Form(...),
    trust_level: str = Form("A"),
    source_type: str = Form("policy"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if trust_level not in VALID_TRUST_LEVELS:
        raise HTTPException(status_code=400, detail=f"trust_level 须为 {VALID_TRUST_LEVELS} 之一")
    if source_type not in VALID_SOURCE_TYPES:
        raise HTTPException(status_code=400, detail=f"source_type 须为 {VALID_SOURCE_TYPES} 之一")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail=f"内容超过 {settings.max_upload_bytes // 1024 // 1024} MB 限制")

    try:
        doc = await ingest_document(
            db, title=title, content=content,
            trust_level=trust_level, source_type=source_type,
        )
        return {"document_id": str(doc.id), "title": doc.title, "trust_level": doc.trust_level}
    except ValueError as e:
        return {"error": str(e), "status": "duplicate"}


@router.get("/knowledge/documents")
async def list_documents(
    trust_level: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Document).order_by(Document.created_at.desc())
    if trust_level:
        stmt = stmt.where(Document.trust_level == trust_level)
    if is_active is not None:
        stmt = stmt.where(Document.is_active == is_active)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    return [{
        "id": str(d.id), "title": d.title,
        "trust_level": d.trust_level, "source_type": d.source_type,
        "knowledge_version": d.knowledge_version, "is_active": d.is_active,
        "valid_from": d.valid_from.isoformat() if d.valid_from else None,
        "valid_to": d.valid_to.isoformat() if d.valid_to else None,
        "created_at": d.created_at.isoformat(),
    } for d in docs]


@router.post("/knowledge/versions/{version}/activate")
async def activate_version(
    version: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(update(Document).values(is_active=False))
    result = await db.execute(
        update(Document)
        .where(Document.knowledge_version == version)
        .values(is_active=True)
        .returning(Document.id)
    )
    await db.commit()
    ids = [str(r[0]) for r in result.fetchall()]
    return {"activated_version": version, "document_count": len(ids), "document_ids": ids}


@router.delete("/knowledge/documents/{doc_id}")
async def delete_document(
    doc_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = await db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    doc.is_active = False
    await db.commit()
    return {"document_id": str(doc_id), "status": "deactivated"}


@router.get("/knowledge/search")
async def search_knowledge(
    q: str,
    top_k: int | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")
    try:
        chunks = await hybrid_search(db, q, top_k)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"检索服务暂不可用: {e}")
    return {"query": q, "results": chunks, "citations": build_citations(chunks)}
