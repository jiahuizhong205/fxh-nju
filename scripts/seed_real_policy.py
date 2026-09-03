"""把南京大学官网抓取的真实辅修政策正文灌入知识库，替代 SAMPLE_POLICIES 编造数据。

数据来源：南京大学教务处《南京大学2021版本科辅修专业培养方案》
（jw.nju.edu.cn 官方 PDF，已用 PyMuPDF 提取到 scripts/fetched/培养方案.txt）
"""

import asyncio
import re

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from apps.api.config import settings
from apps.api.database import Base
from apps.api.models import Document
from services.rag.ingestion import ingest_document

TITLE = "南京大学2021版本科辅修专业培养方案"
SOURCE_URL = "https://jw.nju.edu.cn/_upload/article/files/d4/e5/7bbef4344bada004e61d3e8697f1/321ac63d-1fc2-4ab0-a916-d25e0c124bb9.pdf"
SOURCE_PATH = "scripts/fetched/培养方案.txt"

_SECTION = re.compile(r"^[一二三四五六七八九十]+、")


def _load_body(path: str) -> str:
    """从提取出的 PDF 文本里取政策正文（附件1之前），合并 PDF 硬换行。"""
    raw = open(path, encoding="utf-8").read()
    lines = [l.rstrip() for l in raw.split("\n")]

    body: list[str] = []
    for l in lines:
        if l.strip().startswith("附件1"):
            break
        body.append(l)

    paras: list[str] = []
    buf = ""
    for l in body:
        s = l.strip()
        # 跳过页眉/页脚重复标题
        if s.replace(" ", "") == TITLE:
            continue
        if not s:
            if buf:
                paras.append(buf)
                buf = ""
            continue
        if _SECTION.match(s):
            if buf:
                paras.append(buf)
                buf = ""
            paras.append(s)
            continue
        buf += s
    if buf:
        paras.append(buf)

    return "\n\n".join(paras)


async def main():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        # 清空旧的（编造）政策数据，避免新旧混杂；DocumentChunk 级联删除
        await db.execute(delete(Document))

        content = _load_body(SOURCE_PATH)
        doc = await ingest_document(
            db,
            title=TITLE,
            content=content,
            trust_level="S",
            source_type="policy",
            source_url=SOURCE_URL,
        )
        print(f"OK: {doc.title} (trust={doc.trust_level}, {len(content)} chars)")

    await engine.dispose()
    print("\n真实政策正文已入库！")


if __name__ == "__main__":
    asyncio.run(main())
