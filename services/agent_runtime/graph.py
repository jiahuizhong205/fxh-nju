"""LangGraph 根图：路由、编排、合并。"""

from typing import Any

from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession

from services.agent_runtime.state import AssistantState
from services.agent_runtime.policy_agent import PolicyAgent


async def guard_input(state: AssistantState) -> dict:
    """入口节点：校验输入、注入系统提示。"""
    warnings = []
    msg = state.get("messages", [])
    if not msg:
        warnings.append("空输入")
    return {"warnings": warnings, "intent": "policy"}  # MVP 统一路由到 policy


async def route_intent(state: AssistantState) -> dict:
    """意图路由——MVP 阶段仅支持 policy。"""
    intent = state.get("intent", "policy")
    if intent not in ("policy",):
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
    """根图：编排所有专家子图。MVP 阶段仅加载 Policy Agent。"""

    def __init__(self, db: AsyncSession, checkpointer: Any = None):
        """checkpointer: AsyncPostgresSaver 或其它 LangGraph 兼容 checkpointer。延迟导入以避免强依赖。"""
        self.db = db
        self.policy = PolicyAgent(db)
        self._graph = self._build(checkpointer)

    def _build(self, checkpointer: Any = None) -> StateGraph:
        builder = StateGraph(AssistantState)
        builder.add_node("guard", guard_input)
        builder.add_node("route", route_intent)
        builder.add_node("policy", self.policy.build())
        builder.add_node("respond", build_response)

        builder.add_edge(START, "guard")
        builder.add_edge("guard", "route")
        builder.add_conditional_edges(
            "route",
            lambda s: "policy" if s.get("intent") == "policy" else "policy",
            {"policy": "policy"},
        )
        builder.add_edge("policy", "respond")
        builder.add_edge("respond", END)

        if checkpointer:
            return builder.compile(checkpointer=checkpointer)
        return builder.compile()

    @property
    def compiled(self):
        return self._graph
