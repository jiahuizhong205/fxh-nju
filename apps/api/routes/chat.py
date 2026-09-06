"""对话 API——SSE 流式响应。"""

import json
import logging
from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from apps.api.database import get_db
from apps.api.config import settings
from apps.api.models import Conversation, Message, User, utcnow
from apps.api.routes.auth import get_current_user
from packages.contracts.schemas import ChatRequest, AssistantAnswer
from services.security.input_guard import detect_injection

router = APIRouter()
logger = logging.getLogger("fuxiaohe.chat")


def _mock_result(query: str, intent: str, knowledge_context: dict | None = None) -> dict:
    context_hint = ""
    if knowledge_context and knowledge_context.get("name"):
        context_hint = f"当前知识点：{knowledge_context['name']}（{knowledge_context.get('id', 'unknown')}）。\n"
    return {
        "answer": {
            "content": f"【Mock 回复】已收到你的问题：「{query}」。\n{context_hint}\n当前为本地模拟模式（未接入 LLM），用于无 Ollama 环境下的功能测试。接入真实模型后将返回正式伴学答疑。",
            "citations": [],
        },
        "confidence": 0.0,
        "warnings": ["mock 模式：未调用 LLM"],
    }


SAFE_REPLY = "抱歉，检测到你的输入包含不符合使用规范的内容，我无法继续处理。如有疑问请联系管理员。"


async def _stream_answer(
    db: AsyncSession,
    thread_id: UUID,
    query: str,
    conversation_id: UUID,
    intent: str = "policy",
    knowledge_context: dict | None = None,
    user_id: UUID | None = None,
):
    config = {"configurable": {"thread_id": str(thread_id)}}

    # node_update: 开始检索
    yield f"event: node_update\ndata: {json.dumps({'node': 'retrieve', 'status': 'running', 'message': '正在检索政策文档...'}, ensure_ascii=False)}\n\n"

    try:
        if detect_injection(query):
            result = {
                "answer": {"content": SAFE_REPLY, "citations": []},
                "confidence": 0.0,
                "warnings": ["输入触发安全策略"],
            }
        elif settings.mock_llm:
            result = _mock_result(query, intent, knowledge_context)
        else:
            from langchain_core.messages import HumanMessage

            from services.agent_runtime.graph import RootGraph
            from services.agent_runtime.state import AssistantState

            graph = RootGraph(db).compiled
            state: AssistantState = {
                "user_id": str(user_id),
                "messages": [HumanMessage(content=query)],
                "intent": intent,
                "knowledge_context": knowledge_context or {},
            }
            result = await graph.ainvoke(state, config)
    except Exception:
        logger.exception("chat generation failed")
        yield f"event: error\ndata: {json.dumps({'message': '模型服务暂不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
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
    await db.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=utcnow())
    )
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
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """发送消息，返回 SSE 流。"""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    if len(request.message) > 10000:
        raise HTTPException(status_code=400, detail="消息过长，限制 10000 字符")

    # 创建或获取会话
    if request.thread_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == request.thread_id,
                Conversation.user_id == user.id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="会话不存在")
        conversation_id = request.thread_id
    else:
        conv = Conversation(title=request.message[:30], user_id=user.id)
        db.add(conv)
        await db.flush()
        conversation_id = conv.id

    # 保存用户消息
    user_msg = Message(conversation_id=conversation_id, role="user", content=request.message)
    db.add(user_msg)
    await db.commit()

    thread_id = uuid4()
    knowledge_context = {
        "id": request.knowledge_node_id,
        "name": request.knowledge_node_name,
    }

    return StreamingResponse(
        _stream_answer(
            db,
            thread_id,
            request.message,
            conversation_id,
            request.intent or "policy",
            knowledge_context if any(knowledge_context.values()) else None,
            user.id,
        ),
        media_type="text/event-stream",
        headers={
            "X-Conversation-Id": str(conversation_id),
            "X-Thread-Id": str(thread_id),
            "Cache-Control": "no-cache",
        },
    )


@router.get("/conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取会话列表。"""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    convs = result.scalars().all()
    return [{"id": str(c.id), "title": c.title, "created_at": c.created_at.isoformat()} for c in convs]


@router.get("/conversations/{conv_id}/messages")
async def get_messages(
    conv_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取会话消息历史。"""
    conversation = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id,
            Conversation.user_id == user.id,
        )
    )
    if not conversation.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="会话不存在")
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
