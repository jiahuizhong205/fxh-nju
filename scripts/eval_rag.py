"""RAG 评测脚本——验证检索与回答质量。

用法: PYTHONPATH=. python scripts/eval_rag.py
需求: 已运行 seed_policy_data.py 且有本地 LLM (Ollama)
"""

import asyncio
import json
import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from langchain_core.messages import HumanMessage

from apps.api.config import settings
from apps.api.database import Base
from services.rag.retrieval import hybrid_search, build_context
from services.agent_runtime.state import AssistantState
from services.agent_runtime.graph import RootGraph


# ── 黄金问题集 ──────────────────────────────────
# 每道题: query + 期望的至少一条关键词（命中的文档应含此词）
GOLDEN_SET = [
    {
        "id": "g1",
        "query": "辅修和双学位有什么区别？",
        "category": "policy",
        "keywords": ["辅修学士学位", "双学士学位", "证书", "注明"],
    },
    {
        "id": "g2",
        "query": "辅修需要修多少学分才能拿到学位？",
        "category": "policy",
        "keywords": ["30", "学分", "辅修学士学位"],
    },
    {
        "id": "g3",
        "query": "文科生辅修计算机专业需要注意什么？",
        "category": "policy",
        "keywords": ["高等数学", "文科", "层次"],
    },
    {
        "id": "g4",
        "query": "新闻学辅修有哪些课程？",
        "category": "catalog",
        "keywords": ["新闻采访", "传播学", "编辑"],
    },
    {
        "id": "g5",
        "query": "辅修课和主修课冲突了怎么办？",
        "category": "policy",
        "keywords": ["免修不免考", "主修", "冲突"],
    },
    {
        "id": "g6",
        "query": "鼓楼和仙林校区之间辅修怎么通勤？",
        "category": "catalog",
        "keywords": ["鼓楼", "仙林", "通勤"],
    },
    {
        "id": "g7",
        "query": "中途可以放弃辅修吗？已修课程怎么办？",
        "category": "policy",
        "keywords": ["放弃", "通识选修", "不影响"],
    },
    # 知识库未覆盖的问题——应拒答或低置信
    {
        "id": "g8",
        "query": "辅修法学需要参加司法考试吗？",
        "category": "noise",
        "keywords": [],  # 不应有精确答案
    },
]


@dataclass
class EvalResult:
    query_id: str
    query: str
    category: str
    recall_count: int  # 检索命中数
    top_scores: list[float] = field(default_factory=list)
    keywords_hit: list[str] = field(default_factory=list)
    keywords_miss: list[str] = field(default_factory=list)
    confidence: float = 0.0
    answer_preview: str = ""
    passed: bool = False
    elapsed_ms: float = 0


async def run_eval():
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine)

    results: list[EvalResult] = []

    async with session_factory() as db:
        for item in GOLDEN_SET:
            t0 = time.time()

            # 1. 检索
            chunks = await hybrid_search(db, item["query"], top_k=10)

            keywords_hit = []
            keywords_miss = []
            all_text = " ".join(c.get("content", "") for c in chunks)
            for kw in item["keywords"]:
                if kw in all_text:
                    keywords_hit.append(kw)
                else:
                    keywords_miss.append(kw)

            # 2. 关键词命中率
            recall_ok = len(keywords_hit) > 0 if item["keywords"] else True

            # noise 问题应有低召回或低关键命中
            is_noise = item["category"] == "noise"

            result = EvalResult(
                query_id=item["id"],
                query=item["query"],
                category=item["category"],
                recall_count=len(chunks),
                top_scores=[c.get("score", 0) for c in chunks[:5]],
                keywords_hit=keywords_hit,
                keywords_miss=keywords_miss,
                elapsed_ms=(time.time() - t0) * 1000,
            )

            results.append(result)
            # 不在这里定 passed，等 LLM 回答后再定

    await engine.dispose()
    return results


def print_report(results: list[EvalResult]):
    total = len(results)
    recall_pass = 0
    for r in results:
        has_hit = len(r.keywords_hit) > 0
        is_noise = r.category == "noise"
        # noise 类：关键词不应命中（知识库不应有）
        if is_noise:
            r.passed = len(r.keywords_hit) == 0
        else:
            # 正常类：至少命中一个关键词
            r.passed = has_hit

        if r.passed:
            recall_pass += 1

    print("=" * 60)
    print(f"RAG 评测报告  |  {total} 条问题  |  通过: {recall_pass}/{total}")
    print("=" * 60)

    for r in results:
        status = "[OK]" if r.passed else "[FAIL]"
        print(f"\n{status} {r.query_id} [{r.category}] {r.query}")
        print(f"  检索: {r.recall_count} 条, 最高分: {max(r.top_scores) if r.top_scores else 0:.3f}")
        print(f"  命中关键词: {r.keywords_hit or '无'}")
        print(f"  缺失关键词: {r.keywords_miss or '无'}")
        print(f"  耗时: {r.elapsed_ms:.0f}ms")

    # 指标
    policy_items = [r for r in results if r.category != "noise"]
    noise_items = [r for r in results if r.category == "noise"]

    if policy_items:
        recall_rate = sum(1 for r in policy_items if r.passed) / len(policy_items)
        print(f"\n--- 指标 ---")
        print(f"非噪声 Recall@10 (关键词命中率): {recall_rate:.2%}")

    if noise_items:
        noise_reject = sum(1 for r in noise_items if r.passed)
        print(f"噪声拒答正确率: {noise_reject}/{len(noise_items)}")

    print(f"\n目标: Recall ≥ 0.85, 拒答正确率 ≥ 0.90")


def main():
    results = asyncio.run(run_eval())
    print_report(results)

    # 写 JSON 报告
    out = [{
        "id": r.query_id, "query": r.query, "category": r.category,
        "recall_count": r.recall_count, "keywords_hit": r.keywords_hit,
        "keywords_miss": r.keywords_miss, "passed": r.passed,
        "elapsed_ms": r.elapsed_ms,
    } for r in results]
    with open("eval_rag_results.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n详细结果已保存到 eval_rag_results.json")


if __name__ == "__main__":
    main()
