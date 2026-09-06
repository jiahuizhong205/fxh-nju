"""在配置真实外部 embedding 服务后，重建全部知识库向量。"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.models import DocumentChunk
from services.rag.retrieval import embed_text, embedding_signature


async def main() -> None:
    if settings.mock_llm:
        raise RuntimeError("请先设置 MOCK_LLM=false 并配置外部 embedding 服务")

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        chunks = (await db.execute(select(DocumentChunk).order_by(DocumentChunk.created_at))).scalars().all()
        for index, chunk in enumerate(chunks, start=1):
            chunk.embedding = embed_text(chunk.content)
            chunk.metadata_ = {**(chunk.metadata_ or {}), "embedding_signature": embedding_signature()}
            if index % 25 == 0:
                await db.commit()
                print(f"已重建 {index}/{len(chunks)}")
        await db.commit()
        print(f"向量重建完成：{len(chunks)} 条，签名 {embedding_signature()}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
