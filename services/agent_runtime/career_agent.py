"""职业探索子图——画像→匹配→报告。"""

from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models import StudentProfile
from services.agent_runtime.state import AssistantState
from services.planning.career_engine import match_jobs


CAREER_SYSTEM = """你是福小禾的职业探索助手。帮助学生发现能发挥复合专业背景优势的岗位。

规则：
1. 基于匹配引擎结果，解释每个岗位与学生背景的匹配原因
2. 给出简历优化建议——突出跨学科课程训练和复合能力
3. 提供投递策略和准备建议
4. 明确标注岗位时效性和来源
5. 不自动生成完整的假简历，只提供结构建议和表述示例"""


@dataclass
class CareerAgent:
    db: AsyncSession
    llm: ChatOpenAI | None = None

    def __post_init__(self):
        if self.llm is None:
            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=0.3,
            )

    async def load_profile(self, state: AssistantState) -> dict:
        result = await self.db.execute(
            select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
        )
        p = result.scalar_one_or_none()
        if not p:
            return {"user_profile": {}, "warnings": state.get("warnings", []) + ["未填写画像"]}
        return {"user_profile": {"major": p.major, "career_goals": p.career_goals}}

    async def match(self, state: AssistantState) -> dict:
        profile = state.get("user_profile", {})
        messages = state.get("messages", [])
        query = messages[-1].content if messages else ""

        if not profile:
            return {"candidate_programs": [], "warnings": ["无画像"]}

        major = profile.get("major", "")
        # 从消息中尝试提取辅修专业
        minor = None
        for prog_name in ["新闻学", "法学", "计算机科学与技术", "金融学"]:
            if prog_name in query:
                minor = prog_name
                break

        matches = match_jobs(major, minor)
        return {"candidate_programs": matches}

    async def report(self, state: AssistantState) -> dict:
        profile = state.get("user_profile", {})
        matches = state.get("candidate_programs", [])
        messages = state.get("messages", [])
        query = messages[-1].content if messages else "帮我找适合的实习岗位"

        if not matches:
            return {"answer": {
                "content": "当前岗位库中暂未找到与你的背景精准匹配的岗位。建议扩大搜索范围或完善画像信息。",
                "citations": [], "confidence": 0.0,
            }}

        job_text = "\n\n".join(
            f"[{i+1}] {m['job']['employer']} - {m['job']['title']} "
            f"(匹配度: {m['match_score']}%)\n"
            f"  地点: {m['job']['location']} | 截止: {m['job']['deadline']}\n"
            f"  要求技能: {', '.join(m['job']['skills_required'])}\n"
            f"  优先: {', '.join(m['job']['skills_preferred'])}\n"
            f"  匹配原因: {'; '.join(m['match_reasons']) if m['match_reasons'] else '基础匹配'}"
            for i, m in enumerate(matches[:3])
        )

        response = await self.llm.ainvoke([
            SystemMessage(content=CAREER_SYSTEM),
            HumanMessage(content=f"""学生画像:
  主修: {profile.get('major', '未知')}
  职业目标: {profile.get('career_goals', '未填写')}
  学生问题: {query}

岗位匹配结果:
{job_text}

请生成一份职业探索报告，包括:
1. 推荐岗位总结和匹配度说明
2. 简历优化建议（如何突出复合背景）
3. 投递准备建议
4. 若画像不完整，提示补充方向"""),
        ])

        return {"answer": {"content": response.content, "citations": [], "confidence": 0.7}}

    def build(self) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("load_profile", self.load_profile)
        builder.add_node("match", self.match)
        builder.add_node("report", self.report)
        builder.add_edge(START, "load_profile")
        builder.add_edge("load_profile", "match")
        builder.add_edge("match", "report")
        builder.add_edge("report", END)
        return builder.compile()
