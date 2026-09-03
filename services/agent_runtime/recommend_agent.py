"""辅修推荐子图——画像补全 → 硬过滤 → 评分 → 报告。"""

from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models import StudentProfile
from sqlalchemy import select
from services.agent_runtime.state import AssistantState
from services.planning.recommendation_engine import recommend


SYSTEM_PROMPT = """你是南京大学辅修推荐助手"福小禾"。根据学生画像和推荐引擎结果，生成一份个性化的辅修推荐报告。

规则：
1. 基于引擎计算的结果解释推荐原因
2. 明确标注硬门槛风险和注意事项
3. 列出 Top-N 推荐专业，说明得分和各维度表现
4. 为每个推荐专业列出核心课程、学分、学科评估
5. 若用户信息不完整，列出需要补充的问题

报告格式：简洁结构化，适合本科生阅读。"""


@dataclass
class RecommendAgent:
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
        """加载用户画像——从 DB 取最新记录。"""
        result = await self.db.execute(
            select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
        )
        p = result.scalar_one_or_none()
        if not p:
            return {
                "user_profile": {},
                "warnings": state.get("warnings", []) + ["尚未填写学生画像，请先完善个人信息"],
            }

        profile = {
            "major": p.major, "grade": p.grade, "campus": p.campus,
            "interests": p.interests or [], "strengths": p.strengths or [],
            "career_goals": p.career_goals,
            "math_willingness": p.math_willingness,
            "campus_flexibility": p.campus_flexibility,
            "credit_budget": p.credit_budget,
            "certificate_goal": p.certificate_goal,
        }
        return {"user_profile": profile}

    async def run_recommendation(self, state: AssistantState) -> dict:
        """执行推荐引擎。"""
        profile = state.get("user_profile", {})
        if not profile:
            return {
                "candidate_programs": [],
                "warnings": state.get("warnings", []) + ["无画像数据，无法推荐"],
            }

        # ponytail: 接真实 LLM 时改传 await _load_programs(self.db)，当前读引擎内存常量
        results = recommend(profile)
        return {"candidate_programs": results}

    async def generate_report(self, state: AssistantState) -> dict:
        """生成推荐报告。"""
        profile = state.get("user_profile", {})
        candidates = state.get("candidate_programs", [])
        messages = state.get("messages", [])
        query = messages[-1].content if messages else "请帮我推荐辅修专业"

        if not candidates:
            msg = "当前没有符合条件且不触发硬冲突的辅修专业。"
            if not profile:
                msg = "请先填写学生画像（主修专业、年级、兴趣、目标等），我才能为你推荐适合的辅修方向。"
            return {
                "answer": {
                    "content": msg,
                    "citations": [],
                    "confidence": 0.0,
                },
                "confidence": 0.0,
            }

        # 构建报告数据
        report_lines = []
        for i, r in enumerate(candidates[:3]):
            prog = r["program"]
            lines = [
                f"[{i+1}] {prog['name']}（{prog['discipline']}，学科评估 {prog['subject_rank']}）",
                f"  总分: {r['total_score']:.2f}",
                f"  各维度: 兴趣 {r['scores'].get('interest_fit',0):.0%}, "
                f"职业匹配 {r['scores'].get('career_fit',0):.0%}, "
                f"先修准备 {r['scores'].get('prerequisite_readiness',0):.0%}",
                f"  学分: {prog['total_credits']} | 校区: {prog['campus']}",
                f"  核心课程: {', '.join(prog['core_courses'][:4])}",
            ]
            if r.get("risks"):
                lines.append(f"  ⚠ 注意: {'; '.join(r['risks'])}")
            report_lines.append("\n".join(lines))

        profile_text = "\n".join(f"  {k}: {v}" for k, v in profile.items() if v)
        report_text = "\n\n".join(report_lines)

        prompt = f"""学生画像：
{profile_text}

引擎评分结果：
{report_text}

请基于以上数据生成一份辅修推荐报告，包括：
1. 推荐排序和原因
2. 每个推荐专业的核心优势
3. 需要注意的风险和前置条件
4. 若画像信息不足，提出追问建议"""
        response = await self.llm.ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        return {
            "answer": {
                "content": response.content,
                "citations": [],
                "confidence": candidates[0]["total_score"] if candidates else 0.0,
            },
            "confidence": candidates[0]["total_score"] if candidates else 0.0,
            "warnings": state.get("warnings", []),
        }

    def build(self) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("load_profile", self.load_profile)
        builder.add_node("recommend", self.run_recommendation)
        builder.add_node("report", self.generate_report)
        builder.add_edge(START, "load_profile")
        builder.add_edge("load_profile", "recommend")
        builder.add_edge("recommend", "report")
        builder.add_edge("report", END)
        return builder.compile()
