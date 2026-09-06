from typing import Sequence

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings

def embed_text(text: str) -> list[float]:
    if settings.mock_llm:
        return _placeholder_embedding(text)
    return _embed_via_api(text)


def _placeholder_embedding(text: str) -> list[float]:
    """无 embedding 模型时的占位向量（文本 hash 确定性展开，无语义）。

    ponytail: 上线接真实 embedding API 后重新 seed，替换为真向量。
    """
    import hashlib
    h = hashlib.md5(text.encode("utf-8")).digest()
    return [(b / 127.5 - 1.0) for b in (h * 24)]  # 16 * 24 = 384 维


def embedding_signature() -> str:
    if settings.mock_llm:
        return "mock-hash:384"
    return (
        f"api:{settings.embedding_api_model}:{settings.embedding_dimension}"
        f":request-{settings.embedding_api_dimensions or 'provider-default'}"
    )


def _embed_via_api(text: str) -> list[float]:
    """调用独立配置的 OpenAI 兼容 embedding API。"""
    if not settings.embedding_base_url or not settings.embedding_api_key:
        raise RuntimeError("真实向量服务尚未配置")
    payload = {"model": settings.embedding_api_model, "input": text}
    if settings.embedding_api_dimensions:
        payload["dimensions"] = settings.embedding_api_dimensions
    resp = httpx.post(
        f"{settings.embedding_base_url.rstrip('/')}/embeddings",
        json=payload,
        headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        timeout=settings.embedding_api_timeout_seconds,
    )
    resp.raise_for_status()
    data = resp.json()
    vector = data["data"][0]["embedding"]
    if len(vector) != settings.embedding_dimension:
        raise ValueError(f"向量维度不匹配：期望 {settings.embedding_dimension}，实际 {len(vector)}")
    return vector


async def hybrid_search(
    db: AsyncSession,
    query: str,
    top_k: int | None = None,
    trust_levels: Sequence[str] = ("S", "A"),
) -> list[dict]:
    k = top_k or settings.top_k_retrieval
    query_vector = embed_text(query)

    # pony tail: pgvector cosine + text match union, no cross-encoder re-rank for MVP
    sql = text("""
        WITH vector_matches AS (
            SELECT id, document_id, chunk_index, content, metadata_,
                   1.0 - (embedding <=> cast(:embedding as vector)) AS similarity
            FROM document_chunks
            ORDER BY embedding <=> cast(:embedding as vector)
            LIMIT :k2
        ),
        text_matches AS (
            SELECT id, document_id, chunk_index, content, metadata_,
                   ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', :query)) AS similarity
            FROM document_chunks
            WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', :query)
            LIMIT :k2
        )
        SELECT c.id, c.content, c.chunk_index, c.metadata_,
               d.title, d.trust_level, d.valid_from, d.source_url,
               COALESCE(v.similarity, 0) + COALESCE(t.similarity, 0) AS score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        LEFT JOIN vector_matches v ON c.id = v.id
        LEFT JOIN text_matches t ON c.id = t.id
        WHERE d.trust_level = ANY(:trust_levels)
          AND d.is_active = true
          AND (v.id IS NOT NULL OR t.id IS NOT NULL)
        ORDER BY score DESC
        LIMIT :k
    """)
    result = await db.execute(sql, {
        "embedding": str(query_vector),
        "query": query,
        "k": k, "k2": k * 2,
        "trust_levels": list(trust_levels),
    })
    rows = result.fetchall()
    if not rows:
        return []

    docs = []
    for row in rows:
        docs.append({
            "chunk_id": str(row.id),
            "content": row.content,
            "chunk_index": row.chunk_index,
            "metadata": row.metadata_ or {},
            "document_title": row.title,
            "trust_level": row.trust_level,
            "valid_from": row.valid_from.isoformat() if row.valid_from else None,
            "source_url": row.source_url or "",
            "score": float(row.score),
        })
    return docs


def build_citations(chunks: list[dict]) -> list[dict]:
    return [{
        "citation_id": c["chunk_id"],
        "document_title": c["document_title"],
        "chunk_index": c["chunk_index"],
        "excerpt": c["content"][:200] + ("..." if len(c["content"]) > 200 else ""),
        "trust_level": c["trust_level"],
        "valid_from": c["valid_from"],
        "source_url": c.get("source_url", ""),
    } for c in chunks]


def build_context(chunks: list[dict], max_tokens: int = 3000) -> str:
    parts = []
    for i, c in enumerate(chunks):
        label = c["document_title"]
        parts.append(f"【来源{i+1}】{label}\n{c['content']}")
    return "\n\n".join(parts)
