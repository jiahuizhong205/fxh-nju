"""对话 API——SSE 流式响应。"""

import json
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from langchain_core.messages import HumanMessage

from apps.api.database import get_db
from apps.api.models import Conversation, Message
from packages.contracts.schemas import ChatRequest, AssistantAnswer
from services.agent_runtime.state import AssistantState
from services.agent_runtime.graph import RootGraph

router = APIRouter()


async def _stream_answer(db: AsyncSession, thread_id: UUID, query: str, conversation_id: UUID):
    """SSE 流：node_update → retrieve → generate → final。"""
    graph = RootGraph(db).compiled

    state: AssistantState = {
        "messages": [HumanMessage(content=query)],
        "intent": "policy",
    }

    config = {"configurable": {"thread_id": str(thread_id)}}

    # node_update: 开始检索
    yield f"event: node_update\ndata: {json.dumps({'node': 'retrieve', 'status': 'running', 'message': '正在检索政策文档...'}, ensure_ascii=False)}\n\n"

    try:
        result = await graph.ainvoke(state, config)
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        return

    answer = result.get("answer", {})
    content = answer.get("content", "") if isinstance(answer, dict) else str(answer)
    citations = answer.get("citations", []) if isinstance(answer, dict) else []
    confidence = result.get("confidence", 0.0)
    warnings = result.get("warnings", [])

    # node_update: 检索完成
    yield f"event: node_update\ndata: {json.dumps({'node': 'retrieve', 'status': 'completed', 'message': f'检索到 {len(citations)} 条相关文档'}, ensure_ascii=False)}\n\n"

    # token: 逐段输出（简化：整段输出）
    yield f"event: token\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

    # citation
    for cit in citations:
        yield f"event: citation\ndata: {json.dumps(cit, ensure_ascii=False)}\n\n"

    # 保存 assistant 消息
    msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        citations=citations,
    )
    db.add(msg)
    await db.commit()

    # final
    final = {
        "content": content,
        "citations": citations,
        "confidence": confidence,
        "warnings": warnings,
    }
    yield f"event: final\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """发送消息，返回 SSE 流。"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 创建或获取会话
    if request.thread_id:
        conv = await db.get(Conversation, request.thread_id)
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        conversation_id = request.thread_id
    else:
        conv = Conversation(title=request.message[:30])
        db.add(conv)
        await db.flush()
        conversation_id = conv.id

    # 保存用户消息
    user_msg = Message(conversation_id=conversation_id, role="user", content=request.message)
    db.add(user_msg)
    await db.commit()

    thread_id = uuid4()

    return StreamingResponse(
        _stream_answer(db, thread_id, request.message, conversation_id),
        media_type="text/event-stream",
        headers={
            "X-Conversation-Id": str(conversation_id),
            "X-Thread-Id": str(thread_id),
            "Cache-Control": "no-cache",
        },
    )


@router.get("/conversations")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """获取会话列表。"""
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc()).limit(50)
    )
    convs = result.scalars().all()
    return [{"id": str(c.id), "title": c.title, "created_at": c.created_at.isoformat()} for c in convs]


@router.get("/conversations/{conv_id}/messages")
async def get_messages(conv_id: UUID, db: AsyncSession = Depends(get_db)):
    """获取会话消息历史。"""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    msgs = result.scalars().all()
    return [{
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "citations": m.citations,
        "created_at": m.created_at.isoformat(),
    } for m in msgs]
