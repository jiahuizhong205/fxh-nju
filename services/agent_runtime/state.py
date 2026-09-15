from collections.abc import Awaitable, Callable
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


def merge_evidence(left: list, right: list) -> list:
    by_id = {item["evidence_id"]: item for item in [*left, *right]}
    return list(by_id.values())


class AssistantState(TypedDict, total=False):
    user_id: str
    messages: Annotated[list, add_messages]
    conversation_summary: str
    memory_context: str
    intent: Literal["policy", "recommend", "schedule", "tutor", "career", "multi"]
    knowledge_context: dict
    task_plan: list[dict]
    user_profile: dict
    evidence: Annotated[list[dict], merge_evidence]
    candidate_programs: list[dict]
    study_plan: dict
    answer: dict
    confidence: float
    warnings: list[str]
    pending_approval: dict | None
    token_sink: Callable[[str], Awaitable[None]]


class RequestContext(TypedDict):
    user_id: str
    trace_id: str
    locale: str
    model_profile: str
