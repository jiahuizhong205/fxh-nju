from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class Citation(BaseModel):
    citation_id: str
    document_title: str
    chunk_index: int
    excerpt: str
    trust_level: Literal["S", "A", "B", "C"]
    valid_from: datetime | None = None


class AssistantAnswer(BaseModel):
    content: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str
    thread_id: UUID | None = None


class ChatEvent(BaseModel):
    event: Literal["node_update", "token", "citation", "interrupt", "final", "error"]
    data: dict


class NodeUpdate(BaseModel):
    node: str
    status: Literal["running", "completed", "failed"]
    message: str


class InterruptPayload(BaseModel):
    interrupt_id: str
    question: str
    options: list[str] = Field(default_factory=list)


class KnowledgeIngestResult(BaseModel):
    document_id: UUID
    title: str
    chunks: int
    trust_level: str
