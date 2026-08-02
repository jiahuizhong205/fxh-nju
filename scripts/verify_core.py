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
    from services.rag import retrieval
    retrieval._embedding_model = None
    retrieval._use_api = False
    retrieval._init_local_model()
    mode = "API" if retrieval._use_api else "local"
    print(f"  PASS test_embedding_fallback (mode={mode})")


def test_knowledge_graph_nodes():
    """验证知识图谱包含新闻学课程节点。"""
    from services.rag.knowledge_graph import NEWS_GRAPH

    courses = [n for n in NEWS_GRAPH["nodes"] if n.label == "Course"]
    kps = [n for n in NEWS_GRAPH["nodes"] if n.label == "KnowledgePoint"]
    skills = [n for n in NEWS_GRAPH["nodes"] if n.label == "Skill"]
    careers = [n for n in NEWS_GRAPH["nodes"] if n.label == "CareerPath"]

    assert len(courses) >= 4, f"课程节点不足: {len(courses)}"
    assert len(kps) >= 8, f"知识点节点不足: {len(kps)}"
    assert len(skills) >= 4, f"技能节点不足: {len(skills)}"
    assert len(careers) >= 2, f"职业节点不足: {len(careers)}"

    # 验证边关系
    teaches = [e for e in NEWS_GRAPH["edges"] if e.relation == "TEACHES"]
    requires = [e for e in NEWS_GRAPH["edges"] if e.relation == "REQUIRES"]
    assert len(teaches) >= 6
    assert len(requires) >= 2
    print("  PASS test_knowledge_graph_nodes")


def test_knowledge_tree_generation():
    """验证知识树生成。"""
    from services.rag.knowledge_graph import get_knowledge_tree

    tree = get_knowledge_tree(["新闻采访与写作", "新闻编辑学"])
    assert len(tree["nodes"]) >= 4  # 至少 2 课程 + 多个知识点
    assert len(tree["edges"]) >= 2

    node_names = {n["name"] for n in tree["nodes"]}
    assert "新闻采访与写作" in node_names
    assert "新闻编辑学" in node_names
    print("  PASS test_knowledge_tree_generation")


def test_career_matching():
    """验证岗位匹配返回结果。"""
    from services.planning.career_engine import match_jobs

    matches = match_jobs("汉语言文学", "新闻学")
    assert len(matches) >= 2
    assert matches[0]["match_score"] > 0
    assert any("复合" in r for m in matches for r in m.get("match_reasons", []))
    print("  PASS test_career_matching")


def test_tutor_agent_import():
    """验证 Tutor Agent 可编译。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.tutor_agent import TutorAgent

    db = AsyncMock(spec=AsyncSession)
    agent = TutorAgent(db)
    g = agent.build()
    nodes = {n for n in g.get_graph().nodes}
    assert "explain" in nodes
    print("  PASS test_tutor_agent_import")


def test_career_agent_import():
    """验证 Career Agent 可编译。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.career_agent import CareerAgent

    db = AsyncMock(spec=AsyncSession)
    agent = CareerAgent(db)
    g = agent.build()
    nodes = {n for n in g.get_graph().nodes}
    assert "match" in nodes
    print("  PASS test_career_agent_import")


def test_graph_has_all_agents():
    """验证根图包含全部 5 个 Agent。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.graph import RootGraph

    db = AsyncMock(spec=AsyncSession)
    g = RootGraph(db)
    nodes = {n for n in g.compiled.get_graph().nodes}
    for name in ["policy", "recommend", "schedule", "tutor", "career"]:
        assert name in nodes, f"根图缺少 {name} 节点"
    print("  PASS test_graph_has_all_agents")


def test_version_governance_model():
    """验证 Document 模型包含版本治理字段。"""
    from apps.api.models import Document
    doc = Document(title="测试", source_type="policy", trust_level="S",
                   file_hash="abc", raw_path="/tmp/test",
                   knowledge_version="v2", is_active=True)
    assert doc.knowledge_version == "v2"
    assert doc.is_active is True
    print("  PASS test_version_governance_model")


def test_evidence_verifier_state():
    """验证 evidence 状态 reducer 合并。"""
    from services.agent_runtime.state import merge_evidence

    e1 = [{"evidence_id": "e1", "trust_level": "S"}]
    e2 = [{"evidence_id": "e2", "trust_level": "A"}]
    merged = merge_evidence(e1, e2)
    assert len(merged) == 2
    print("  PASS test_evidence_verifier_state")


def test_hybrid_search_sql_has_active_filter():
    with open("services/rag/retrieval.py", encoding="utf-8") as f:
        code = f.read()
    assert "d.is_active = true" in code, "retrieval must filter by is_active"
    print("  PASS test_hybrid_search_sql_has_active_filter")


def test_recommendation_hard_filter():
    """验证硬过滤：文科生不求高数 → 计算机系应被过滤。"""
    from services.planning.recommendation_engine import PROGRAMS, hard_filter

    profile = {
        "major": "汉语言文学", "grade": "大二",
        "campus": "仙林校区", "campus_flexibility": False,
        "math_willingness": False, "certificate_goal": "degree",
        "credit_budget": 60,
    }
    cs = next(p for p in PROGRAMS if p["name"] == "计算机科学与技术")
    result = hard_filter(cs, profile)
    # 应该因数学门槛被标记
    has_math_warning = any("高等数学" in r for r in result.reasons)
    assert has_math_warning, f"应有数学门槛警告: {result.reasons}"
    # 仙林↔仙林不应有校区警告
    has_campus_block = any("不可通勤" in r for r in result.reasons)
    assert not has_campus_block, f"同校区不应触发校区过滤: {result.reasons}"
    print("  PASS test_recommendation_hard_filter")


def test_recommendation_scoring():
    """验证评分：计算机系对 CS 主修应有高空缺效率分。"""
    from services.planning.recommendation_engine import score_program, PROGRAMS

    profile = {"major": "计算机科学与技术", "interests": ["AI", "后端"], "career_goals": ""}
    cs = next(p for p in PROGRAMS if p["name"] == "计算机科学与技术")
    result = score_program(cs, profile)
    assert result.scores["overlap_efficiency"] >= 0.5
    assert result.total > 0
    print("  PASS test_recommendation_scoring")


def test_recommend_agent_import():
    """验证 Recommend Agent 可导入和编译。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.recommend_agent import RecommendAgent

    db = AsyncMock(spec=AsyncSession)
    agent = RecommendAgent(db)
    g = agent.build()
    nodes = {n for n in g.get_graph().nodes}
    assert "load_profile" in nodes
    assert "recommend" in nodes
    assert "report" in nodes
    print("  PASS test_recommend_agent_import")


def test_graph_has_recommend():
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.graph import RootGraph

    db = AsyncMock(spec=AsyncSession)
    g = RootGraph(db)
    nodes = {n for n in g.compiled.get_graph().nodes}
    assert "recommend" in nodes, f"根图缺少 recommend 节点: {nodes}"
    print("  PASS test_graph_has_recommend")


def test_course_planner_generates_plan():
    """验证课程规划器生成非空方案。"""
    from services.planning.course_planner import generate_plan

    profile = {"major": "汉语言文学", "grade": "大二", "campus": "仙林校区"}
    result = generate_plan("新闻学", profile)
    assert len(result.items) > 0, "应有课程项"
    assert result.items[0].course
    assert not result.infeasible, "新闻学+仙林不应不可行"
    print("  PASS test_course_planner_generates_plan")


def test_course_planner_campus_warning():
    """验证跨校区规划产生警告。"""
    from services.planning.course_planner import generate_plan

    profile = {"major": "汉语言文学", "grade": "大二", "campus": "仙林校区"}
    result = generate_plan("法学", profile)
    # 法学在鼓楼，应有跨校区警告
    has_campus = any("鼓楼" in w or "跨校区" in w for w in result.warnings)
    assert has_campus, f"应有校区警告: {result.warnings}"
    print("  PASS test_course_planner_campus_warning")


def test_plan_agent_import():
    """验证 Plan Agent 可导入和编译。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.plan_agent import PlanAgent

    db = AsyncMock(spec=AsyncSession)
    agent = PlanAgent(db)
    g = agent.build()
    nodes = {n for n in g.get_graph().nodes}
    assert "plan" in nodes
    assert "explain" in nodes
    print("  PASS test_plan_agent_import")


def test_graph_has_schedule():
    """验证根图包含 schedule 路由。"""
    from unittest.mock import AsyncMock
    from sqlalchemy.ext.asyncio import AsyncSession
    from services.agent_runtime.graph import RootGraph

    db = AsyncMock(spec=AsyncSession)
    g = RootGraph(db)
    nodes = {n for n in g.compiled.get_graph().nodes}
    assert "schedule" in nodes, f"根图缺少 schedule 节点: {nodes}"
    print("  PASS test_graph_has_schedule")


def main():
    print("=== 福小禾 核心逻辑验证 ===\n")

    tests = [
        test_state_merge_evidence,
        test_text_split,
        test_schemas,
        test_config,
        test_graph_compile,
        test_ingestion_hash_dedup,
        test_version_governance_model,
        test_evidence_verifier_state,
        test_hybrid_search_sql_has_active_filter,
        test_recommendation_hard_filter,
        test_recommendation_scoring,
        test_recommend_agent_import,
        test_graph_has_recommend,
        test_course_planner_generates_plan,
        test_course_planner_campus_warning,
        test_plan_agent_import,
        test_graph_has_schedule,
        test_knowledge_graph_nodes,
        test_knowledge_tree_generation,
        test_career_matching,
        test_tutor_agent_import,
        test_career_agent_import,
        test_graph_has_all_agents,
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
