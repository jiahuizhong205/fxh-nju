"""导入经人工收集和提取的学生手册正文到政策知识库。

2025 版作为当前有效版本参与检索；2024 版保留为历史档案，不参与默认检索，
避免旧规与现行规则混答。2025 本科辅修培养方案已经由
sync_official_minor_data.py 以官网来源 S 级导入，因此不在此重复导入。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.database import Base
from apps.api.models import Document
from services.rag.ingestion import ingest_document


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    {
        "title": "南京大学2025版学生手册（本科生部分）",
        "path": ROOT / "scripts/fetched/policies/nju-student-handbook-2025.txt",
        "raw_path": "repository://scripts/fetched/policies/nju-student-handbook-2025.txt",
        "trust_level": "A",
        "source_type": "regulation",
        "valid_from": datetime(2025, 9, 1),
        "valid_to": None,
        "is_active": True,
    },
    {
        "title": "南京大学2024学生手册（本科生部分）",
        "path": ROOT / "scripts/fetched/policies/nju-student-handbook-2024.txt",
        "raw_path": "repository://scripts/fetched/policies/nju-student-handbook-2024.txt",
        "trust_level": "A",
        "source_type": "regulation",
        "valid_from": datetime(2024, 9, 1),
        "valid_to": datetime(2025, 8, 31),
        "is_active": False,
    },
)


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        for source in SOURCES:
            content = source["path"].read_text(encoding="utf-8")
            existing = (await db.execute(
                select(Document).where(Document.raw_path == source["raw_path"])
            )).scalar_one_or_none()
            if existing:
                print(f"SKIP: {source['title']} 已存在")
                continue

            doc = await ingest_document(
                db,
                title=source["title"],
                content=content,
                trust_level=source["trust_level"],
                source_type=source["source_type"],
                valid_from=source["valid_from"],
                valid_to=source["valid_to"],
                raw_path=source["raw_path"],
                is_active=source["is_active"],
            )
            print(f"OK: {doc.title} (active={doc.is_active}, {len(content)} chars)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
