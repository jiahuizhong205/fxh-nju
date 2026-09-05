"""课程规划子图——加载画像 → 生成规划 → 验证方案。"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import settings
from apps.api.models import StudentProfile
from services.agent_runtime.state import AssistantState
from services.planning.course_planner import generate_plan, PROGRAM_PLANS


@dataclass
class PlanAgent:
    db: AsyncSession
    llm: ChatOpenAI | None = None

    def __post_init__(self):
        if self.llm is None and not settings.mock_llm:
            from langchain_openai import ChatOpenAI

            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=0.2,
            )

    async def load_profile(self, state: AssistantState) -> dict:
        result = await self.db.execute(
            select(StudentProfile).order_by(StudentProfile.updated_at.desc()).limit(1)
        )
        p = result.scalar_one_or_none()
        if not p:
            return {
                "user_profile": {},
                "warnings": state.get("warnings", []) + ["尚未填写学生画像"],
            }
        return {"user_profile": {
            "major": p.major, "grade": p.grade, "campus": p.campus,
            "campus_flexibility": p.campus_flexibility,
            "credit_budget": p.credit_budget,
            "schedule_preferences": p.schedule_preferences,
        }}

    async def plan(self, state: AssistantState) -> dict:
        profile = state.get("user_profile", {})
        if not profile:
            return {
                "study_plan": {},
                "warnings": state.get("warnings", []) + ["无画像数据"],
            }

        # 从消息中提取目标辅修专业
        messages = state.get("messages", [])
        query = messages[-1].content if messages else ""
        program_name = ""
        for name in PROGRAM_PLANS:
            if name in query:
                program_name = name
                break

        if not program_name:
            return {
                "study_plan": {},
                "warnings": state.get("warnings", []) + ["请指定要规划的辅修专业名称"],
                "available_programs": list(PROGRAM_PLANS.keys()),
            }

        # ponytail: 接真实 LLM 时改传 await _load_plans(self.db)，当前读引擎内存常量
        result = generate_plan(program_name, profile)
        return {"study_plan": {
            "program": result.program_name,
            "items": [{
                "semester": it.semester, "term": it.term, "year": it.year,
                "course": it.course, "credits": it.credits, "campus": it.campus,
            } for it in result.items],
            "alternatives": [[{
                "semester": it.semester, "term": it.term, "year": it.year,
                "course": it.course, "credits": it.credits, "campus": it.campus,
            } for it in alt] for alt in result.alternatives],
            "warnings": result.warnings,
            "infeasible": result.infeasible,
        }, "warnings": result.warnings}

    async def explain(self, state: AssistantState) -> dict:
        study_plan = state.get("study_plan", {})
        warnings = state.get("warnings", [])
        messages = state.get("messages", [])

        if not study_plan:
            query = messages[-1].content if messages else ""
            available = list(PROGRAM_PLANS.keys())
            return {
                "answer": {
                    "content": f"请指定要规划的辅修专业。当前支持: {', '.join(PROGRAM_PLANS.keys())}",
                    "citations": [],
                    "confidence": 0.0,
                },
            }

        items = study_plan.get("items", [])
        lines = []
        for it in items:
            lines.append(f"- 第{it['year']}学年 {it['term']}: {it['course']} ({it['credits']}学分, {it['campus']})")

        plan_text = "\n".join(lines)
        warn_text = "\n".join(f"- {w}" for w in warnings) if warnings else "无冲突"

        from langchain_core.messages import HumanMessage, SystemMessage

        response = await self.llm.ainvoke([
            SystemMessage(content="你是课程规划助手。用简洁清晰的方式呈现辅修课程时间轴，标注校区和风险。"),
            HumanMessage(content=f"""辅修专业: {study_plan.get('program')}

课程安排:
{plan_text}

注意事项:
{warn_text}

请撰写一段友好的课程规划总结，突出：
1. 总学分数和学期分布
2. 校区通勤提示
3. 每学期辅修学分负荷
4. 如有备选方案简要说明"""),
        ])

        return {
            "answer": {
                "content": response.content,
                "citations": [],
                "confidence": 0.8,
            },
            "warnings": warnings,
        }

    def build(self) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("load_profile", self.load_profile)
        builder.add_node("plan", self.plan)
        builder.add_node("explain", self.explain)
        builder.add_edge(START, "load_profile")
        builder.add_edge("load_profile", "plan")
        builder.add_edge("plan", "explain")
        builder.add_edge("explain", END)
        return builder.compile()
