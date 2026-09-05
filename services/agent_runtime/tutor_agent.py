"""伴学子图——知识树生成 → 讲解 → 测验 → 进度。"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models import StudentProfile
from services.agent_runtime.state import AssistantState
from services.rag.knowledge_graph import get_knowledge_tree


TUTOR_SYSTEM = """你是福小禾的伴学助手。根据学生的知识树和主修专业背景，用跨学科类比帮助理解辅修知识点。

规则：
1. 知识点讲解时，优先用学生主修专业的思维框架做类比（如用文学分析框架解释新闻编辑）
2. 对零基础学生从最基础概念开始，逐步深入
3. 每个知识点讲解后出一道诊断题
4. 回答简洁、鼓励性强
5. 独立自学模式强调自学资源、学习路线和进度管理"""


@dataclass
class TutorAgent:
    db: AsyncSession
    llm: ChatOpenAI | None = None

    def __post_init__(self):
        if self.llm is None and not settings.mock_llm:
            from langchain_openai import ChatOpenAI

            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=0.5,
            )

    async def load_context(self, state: AssistantState) -> dict:
        """加载学生画像和学习上下文。"""
        result = await self.db.execute(
            select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
        )
        p = result.scalar_one_or_none()
        profile = {}
        if p:
            profile = {"major": p.major, "grade": p.grade}

        messages = state.get("messages", [])
        query = messages[-1].content if messages else ""
        knowledge_context = state.get("knowledge_context", {})

        # 判断模式
        mode = "self_study" if "自学" in query else "enrolled"
        if state.get("user_profile", {}).get("certificate_goal") == "degree":
            mode = "enrolled"

        return {
            "user_profile": profile,
            "_tutor_mode": mode,
            "_knowledge_context": knowledge_context,
        }

    async def build_knowledge_tree(self, state: AssistantState) -> dict:
        """从消息中提取课程名，构建知识树。"""
        messages = state.get("messages", [])
        query = messages[-1].content if messages else ""

        course_map = {
            "新闻": ["新闻采访与写作", "传播学概论", "新闻编辑学", "媒介伦理与法规", "数据新闻", "新闻评论"],
            "法学": ["法理学", "宪法学", "民法学", "刑法学", "行政法学", "经济法学"],
            "计算机": ["程序设计基础", "数据结构", "计算机系统基础", "数据库概论", "计算机网络"],
            "金融": ["微观经济学", "宏观经济学", "会计学", "公司金融", "投资学", "金融市场学"],
        }
        matched = []
        for key, courses in course_map.items():
            if key in query:
                matched = courses
                break

        if not matched:
            matched = course_map.get("新闻", [])  # 默认新闻学

        tree = get_knowledge_tree(matched)
        return {"_knowledge_tree": tree}

    async def explain(self, state: AssistantState) -> dict:
        """生成个性化讲解。"""
        profile = state.get("user_profile", {})
        tree = state.get("_knowledge_tree", {})
        messages = state.get("messages", [])
        query = messages[-1].content if messages else "请开始伴学"
        mode = state.get("_tutor_mode", "self_study")
        knowledge_context = state.get("_knowledge_context", {})

        nodes = tree.get("nodes", [])
        edges = tree.get("edges", [])

        kp_nodes = [n for n in nodes if n["label"] == "KnowledgePoint"]
        kp_list = "\n".join(
            f"- {n['name']} (难度: {tree.get('properties', {}).get('difficulty', '?')})"
            for n in kp_nodes[:12]
        )

        preq_edges = [e for e in edges if e["relation"] == "REQUIRES"]
        preq_text = "\n".join(
            f"  {e['source']} → {e['target']}" for e in preq_edges[:10]
        )

        mode_text = "在校辅修模式——结合主修教材做跨学科讲解" if mode == "enrolled" else "独立自学模式——强调自学路线和资源"
        context_text = (
            f"当前用户点击的知识点：{knowledge_context.get('name')}（节点 {knowledge_context.get('id')}）"
            if knowledge_context.get("name") else "当前没有指定知识点"
        )

        prompt = f"""学生主修: {profile.get('major', '未知')}
模式: {mode_text}
学生问题: {query}
{context_text}

知识点树:
{kp_list or '(暂无可展示的知识点)'}

先修依赖:
{preq_text or '(无)'}

请：
1. 用学生能理解的跨学科类比解释核心概念
2. 按先修顺序推荐学习路径
3. 对每个阶段提出一个可操作的学习任务
4. 语气鼓励、像学长学姐一样"""

        from langchain_core.messages import HumanMessage, SystemMessage

        response = await self.llm.ainvoke([
            SystemMessage(content=TUTOR_SYSTEM),
            HumanMessage(content=prompt),
        ])

        return {"answer": {"content": response.content, "citations": [], "confidence": 0.75}}

    def build(self) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("load_context", self.load_context)
        builder.add_node("build_tree", self.build_knowledge_tree)
        builder.add_node("explain", self.explain)
        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "build_tree")
        builder.add_edge("build_tree", "explain")
        builder.add_edge("explain", END)
        return builder.compile()
