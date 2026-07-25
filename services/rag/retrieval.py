from typing import Sequence

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings

# ponytail: local embedding first, fall back to API if model unavailable (e.g. no HF access)
_embedding_model = None
_use_api = False


def _init_local_model():
    global _embedding_model, _use_api
    if _embedding_model is not None or _use_api:
        return
    # 仅尝试本地缓存，不触发下载（国内 HF 不通会卡很久）
    try:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(settings.embedding_model, local_files_only=True)
    except Exception:
        _use_api = True


def embed_text(text: str) -> list[float]:
    _init_local_model()
    if _use_api:
        return _embed_via_api(text)
    return _embedding_model.encode(text, normalize_embeddings=True).tolist()


def _embed_via_api(text: str) -> list[float]:
    """OpenAI 兼容 embedding API 兜底。"""
    resp = httpx.post(
        f"{settings.llm_base_url}/embeddings",
        json={"model": settings.llm_model, "input": text},
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


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
                   1.0 - (embedding <=> :embedding) AS similarity
            FROM document_chunks
            ORDER BY embedding <=> :embedding
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
               d.title, d.trust_level, d.valid_from,
               COALESCE(v.similarity, 0) + COALESCE(t.similarity, 0) AS score
        FROM document_chunks c
        JOIN documents d ON c.document_id = d.id
        LEFT JOIN vector_matches v ON c.id = v.id
        LEFT JOIN text_matches t ON c.id = t.id
        WHERE d.trust_level = ANY(:trust_levels)
          AND (v.id IS NOT NULL OR t.id IS NOT NULL)
        ORDER BY score DESC
        LIMIT :k
    """)
    result = await db.execute(sql, {
        "embedding": query_vector,
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
    } for c in chunks]


def build_context(chunks: list[dict], max_tokens: int = 3000) -> str:
    parts = []
    for i, c in enumerate(chunks):
        label = c["document_title"]
        parts.append(f"【来源{i+1}】{label}\n{c['content']}")
    return "\n\n".join(parts)
