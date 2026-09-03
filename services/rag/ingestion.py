"""文档摄取：解析、切分、向量化写入。"""

import hashlib
import re
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models import Document, DocumentChunk
from apps.api.config import settings
from services.rag.retrieval import embed_text


def split_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    cs = chunk_size or settings.chunk_size
    ol = overlap or settings.chunk_overlap

    # 按段落优先切分，段落过长再按句切
    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) < cs:
            buf += ("\n" + para) if buf else para
        else:
            if buf:
                chunks.append(buf)
            # 段落超长，按句切
            if len(para) > cs:
                sentences = re.split(r"(?<=[。！？；])", para)
                sub = ""
                for s in sentences:
                    if len(sub) + len(s) < cs:
                        sub += s
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = s
                if sub:
                    buf = sub
                else:
                    buf = ""
            else:
                buf = para
    if buf:
        chunks.append(buf)

    # 添加重叠
    if ol > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev = chunks[i - 1]
            curr = chunks[i]
            overlap_text = prev[-ol:] if len(prev) > ol else prev
            overlapped.append(overlap_text + "\n" + curr)
        chunks = overlapped

    return chunks


async def ingest_document(
    db: AsyncSession,
    title: str,
    content: str,
    trust_level: str = "A",
    source_type: str = "policy",
    valid_from: str | None = None,
    valid_to: str | None = None,
    source_url: str = "",
) -> Document:
    file_hash = hashlib.sha256(content.encode()).hexdigest()

    # 检查是否已存在
    existing = await db.execute(select(Document).where(Document.file_hash == file_hash))
    if existing.scalar_one_or_none():
        raise ValueError(f"文档 {title} 已存在 (hash={file_hash[:12]})")

    doc = Document(
        title=title,
        source_type=source_type,
        trust_level=trust_level,
        file_hash=file_hash,
        raw_path=f"minio://raw/{title}",
        source_url=source_url,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    db.add(doc)
    await db.flush()

    chunks = split_text(content)
    for i, chunk_text in enumerate(chunks):
        if not chunk_text.strip():
            continue
        embedding = embed_text(chunk_text)
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            content=chunk_text,
            embedding=embedding,
            metadata_={"title": title, "trust_level": trust_level},
        )
        db.add(chunk)

    await db.commit()
    return doc
