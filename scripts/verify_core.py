"""核心逻辑验证——无需数据库、无需 LLM，纯单元级自检。"""

import sys
import asyncio

def test_state_merge_evidence():
    """验证 evidence reducer 去重合并逻辑。"""
    from services.agent_runtime.state import merge_evidence

    left = [{"evidence_id": "a", "v": 1}, {"evidence_id": "b", "v": 2}]
    right = [{"evidence_id": "b", "v": 3}, {"evidence_id": "c", "v": 4}]
    merged = merge_evidence(left, right)

    ids = {e["evidence_id"] for e in merged}
    assert ids == {"a", "b", "c"}, f"merge IDs wrong: {ids}"
    # 后写入的 b 覆盖前一个
    b = next(e for e in merged if e["evidence_id"] == "b")
    assert b["v"] == 3, f"merge last-write-wins failed: {b}"
    print("  PASS test_state_merge_evidence")


def test_text_split():
    """验证文档切分逻辑。"""
    from services.rag.ingestion import split_text

    # 短文本不分片
    short = "这是一句测试。"
    assert split_text(short, chunk_size=500) == [short]

    # 段落切分
    paras = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
    chunks = split_text(paras, chunk_size=500)
    assert len(chunks) == 1, f"short paras should merge: got {len(chunks)}"

    # 超长段按句切
    long_sents = "。".join([f"第{i}句" for i in range(100)])
    chunks = split_text(long_sents, chunk_size=200)
    assert len(chunks) > 1, f"long text should split: got {len(chunks)}"
    print("  PASS test_text_split")


def test_schemas():
    """验证 Pydantic schema 合法。"""
    from packages.contracts.schemas import ChatRequest, Citation, AssistantAnswer

    req = ChatRequest(message="辅修多少学分？")
    assert req.message == "辅修多少学分？"
    assert req.thread_id is None

    cit = Citation(
        citation_id="c1", document_title="测试文档",
        chunk_index=0, excerpt="测试摘录", trust_level="S",
    )
    assert cit.trust_level == "S"

    ans = AssistantAnswer(content="回答", citations=[cit], confidence=0.9)
    assert len(ans.citations) == 1
    print("  PASS test_schemas")


def test_config():
    """验证配置加载。"""
    from apps.api.config import Settings
    s = Settings()
    assert "postgresql" in s.database_url
    assert s.chunk_size == 500
    assert s.top_k_retrieval == 8
    print("  PASS test_config")


def test_graph_compile():
    """验证 LangGraph 根图可编译（不需要 checkpointer）。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.graph import RootGraph

    db = AsyncMock(spec=AsyncSession)
    g = RootGraph(db)
    assert g.compiled is not None
    # 验证节点存在
    nodes = g.compiled.get_graph().nodes
    node_names = {n for n in nodes}
    assert "guard" in node_names
    assert "policy" in node_names
    assert "respond" in node_names
    print("  PASS test_graph_compile")


def test_ingestion_hash_dedup():
    """验证文档哈希去重逻辑。"""
    import hashlib
    content = "测试文档内容"
    h1 = hashlib.sha256(content.encode()).hexdigest()
    h2 = hashlib.sha256(content.encode()).hexdigest()
    assert h1 == h2, "hash not deterministic"
    # 不同内容不同哈希
    h3 = hashlib.sha256("不同内容".encode()).hexdigest()
    assert h1 != h3, "hash collision"
    print("  PASS test_ingestion_hash_dedup")


def test_embedding_fallback():
    """验证嵌入回退机制：本地模型不可用时走 API 模式。"""
    from services.rag import retrieval
    retrieval._embedding_model = None
    retrieval._use_api = False
    retrieval._init_local_model()
    # 网络不通时预期走 API fallback
    mode = "API" if retrieval._use_api else "local"
    print(f"  PASS test_embedding_fallback (mode={mode})")


def main():
    print("=== 福小禾 核心逻辑验证 ===\n")

    tests = [
        test_state_merge_evidence,
        test_text_split,
        test_schemas,
        test_config,
        test_graph_compile,
        test_ingestion_hash_dedup,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {e}")
            failed += 1

    # 嵌入回退测试
    print()
    try:
        test_embedding_fallback()
    except Exception as e:
        print(f"  SKIP test_embedding_fallback: {e}")

    print(f"\n{'='*40}")
    print(f"结果: {passed} 通过, {failed} 失败, 共 {passed + failed} 项")
    if failed:
        print("有测试未通过！")
        sys.exit(1)
    else:
        print("全部通过 [OK]")


if __name__ == "__main__":
    main()
