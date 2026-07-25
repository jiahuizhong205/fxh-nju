"""知识库管理 API——文档上传与摄取。"""

from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.database import get_db
from services.rag.ingestion import ingest_document

router = APIRouter()


@router.post("/knowledge/documents")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    trust_level: str = Form("A"),
    source_type: str = Form("policy"),
    db: AsyncSession = Depends(get_db),
):
    """上传政策文档并摄入知识库。"""
    content = await file.read()
    text = content.decode("utf-8")

    try:
        doc = await ingest_document(
            db, title=title, content=text,
            trust_level=trust_level, source_type=source_type,
        )
        return {
            "document_id": str(doc.id),
            "title": doc.title,
            "trust_level": doc.trust_level,
        }
    except ValueError as e:
        return {"error": str(e), "status": "duplicate"}


@router.post("/knowledge/documents/text")
async def ingest_text(
    title: str = Form(...),
    content: str = Form(...),
    trust_level: str = Form("A"),
    source_type: str = Form("policy"),
    db: AsyncSession = Depends(get_db),
):
    """通过文本内容摄入知识。"""
    try:
        doc = await ingest_document(
            db, title=title, content=content,
            trust_level=trust_level, source_type=source_type,
        )
        return {
            "document_id": str(doc.id),
            "title": doc.title,
            "trust_level": doc.trust_level,
        }
    except ValueError as e:
        return {"error": str(e), "status": "duplicate"}
