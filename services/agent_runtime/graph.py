"""LangGraph 根图：路由、编排、合并。"""

from typing import Any

from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession

from services.agent_runtime.state import AssistantState
from services.agent_runtime.policy_agent import PolicyAgent
from services.agent_runtime.recommend_agent import RecommendAgent
from services.agent_runtime.plan_agent import PlanAgent


async def guard_input(state: AssistantState) -> dict:
    warnings = []
    msg = state.get("messages", [])
    if not msg:
        warnings.append("空输入")
    if not state.get("intent"):
        return {"warnings": warnings, "intent": "policy"}
    return {"warnings": warnings}


async def route_intent(state: AssistantState) -> dict:
    intent = state.get("intent", "policy")
    valid = {"policy", "recommend", "schedule"}
    if intent not in valid:
        intent = "policy"
    return {"intent": intent}


async def build_response(state: AssistantState) -> dict:
    """构造最终响应。"""
    answer = state.get("answer", {})
    content = answer.get("content", "") if isinstance(answer, dict) else str(answer)
    return {
        "answer": {
            "content": content,
            "citations": answer.get("citations", []) if isinstance(answer, dict) else [],
            "confidence": state.get("confidence", 0.0),
        }
    }


class RootGraph:
    def __init__(self, db: AsyncSession, checkpointer: Any = None):
        self.db = db
        self.policy = PolicyAgent(db)
        self.recommend = RecommendAgent(db)
        self.plan = PlanAgent(db)
        self._graph = self._build(checkpointer)

    def _build(self, checkpointer: Any = None) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("guard", guard_input)
        builder.add_node("route", route_intent)
        builder.add_node("policy", self.policy.build())
        builder.add_node("recommend", self.recommend.build())
        builder.add_node("schedule", self.plan.build())
        builder.add_node("respond", build_response)

        builder.add_edge(START, "guard")
        builder.add_edge("guard", "route")
        builder.add_conditional_edges(
            "route",
            lambda s: s.get("intent", "policy"),
            {"policy": "policy", "recommend": "recommend", "schedule": "schedule"},
        )
        builder.add_edge("policy", "respond")
        builder.add_edge("recommend", "respond")
        builder.add_edge("schedule", "respond")
        builder.add_edge("respond", END)

        if checkpointer:
            return builder.compile(checkpointer=checkpointer)
        return builder.compile()

    @property
    def compiled(self):
        return self._graph
