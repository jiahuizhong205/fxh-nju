"""对话 API——SSE 流式响应。"""

import asyncio
import json
import logging
from uuid import uuid4, UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from apps.api.database import get_db
from apps.api.config import settings
from apps.api.models import Conversation, Message, User, utcnow
from apps.api.routes.auth import get_current_user
from packages.contracts.schemas import ChatRequest, AssistantAnswer
from services.memory.conversation import load_conversation_context
from services.memory import maintenance as memory_maintenance
from services.memory.maintenance import memory_auto_capture_enabled
from services.memory.retrieval import format_memory_context, retrieve_relevant_memories
from services.security.input_guard import detect_injection

router = APIRouter()
logger = logging.getLogger("fuxiaohe.chat")

async def invoke_graph_with_timeout(graph, state, config):
    """为整条智能体链路设置边界，避免 SSE 无期限挂起。"""
    return await asyncio.wait_for(
        graph.ainvoke(state, config),
        timeout=settings.agent_response_timeout_seconds,
    )


async def stream_graph_events(graph, state, config):
    """并发运行图，把模型片段和最终结果按产生顺序交给 SSE。"""
    queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue()

    async def emit_token(content: str) -> None:
        if content:
            await queue.put(("token", content))

    async def run_graph() -> None:
        try:
            streamed_state = {**state, "token_sink": emit_token}
            result = await invoke_graph_with_timeout(graph, streamed_state, config)
            await queue.put(("result", result))
        except BaseException as exc:
            await queue.put(("error", exc))

    task = asyncio.create_task(run_graph())
    try:
        while True:
            event_type, payload = await queue.get()
            if event_type == "error":
                raise payload
            yield event_type, payload
            if event_type == "result":
                break
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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
    user_preferences: dict | None = None,
    latest_user_message_id: UUID | None = None,
    background_tasks: BackgroundTasks | None = None,
):
    config = {"configurable": {"thread_id": str(thread_id)}}
    streamed_tokens = False
    injection_rejected = False

    # node_update: 开始检索
    yield f"event: node_update\ndata: {json.dumps({'node': 'retrieve', 'status': 'running', 'message': '正在检索政策文档...'}, ensure_ascii=False)}\n\n"

    try:
        if detect_injection(query):
            injection_rejected = True
            result = {
                "answer": {"content": SAFE_REPLY, "citations": []},
                "confidence": 0.0,
                "warnings": ["输入触发安全策略"],
            }
        elif settings.mock_llm:
            result = _mock_result(query, intent, knowledge_context)
        else:
            from services.agent_runtime.graph import RootGraph
            from services.agent_runtime.state import AssistantState

            graph = RootGraph(db).compiled
            context = await load_conversation_context(db, conversation_id)
            messages = context.messages
            if not messages:
                from langchain_core.messages import HumanMessage

                messages = [HumanMessage(content=query)]
            memory_context = ""
            if user_id is not None and memory_auto_capture_enabled(user_preferences or {}):
                try:
                    memories = await retrieve_relevant_memories(db, user_id, query, intent)
                    memory_context = format_memory_context(
                        memories,
                        settings.memory_context_character_budget,
                    )
                except Exception as exc:
                    logger.warning(
                        "chat memory retrieval failed conversation_id=%s user_id=%s error_type=%s",
                        conversation_id,
                        user_id,
                        type(exc).__name__,
                    )
                    try:
                        await db.rollback()
                    except Exception as rollback_exc:
                        logger.error(
                            "chat memory retrieval rollback failed conversation_id=%s user_id=%s "
                            "error_type=%s",
                            conversation_id,
                            user_id,
                            type(rollback_exc).__name__,
                        )
            state: AssistantState = {
                "user_id": str(user_id),
                "messages": messages,
                "intent": intent,
                "knowledge_context": knowledge_context or {},
                "conversation_summary": context.summary,
                "memory_context": memory_context,
            }
            yield f"event: node_update\ndata: {json.dumps({'node': 'generate', 'status': 'running', 'message': '正在根据政策原文生成回答...'}, ensure_ascii=False)}\n\n"
            async for event_type, payload in stream_graph_events(graph, state, config):
                if event_type == "token":
                    streamed_tokens = True
                    yield f"event: token\ndata: {json.dumps({'content': payload}, ensure_ascii=False)}\n\n"
                else:
                    result = payload
    except asyncio.TimeoutError:
        logger.warning("chat generation timed out after %ss", settings.agent_response_timeout_seconds)
        yield f"event: error\ndata: {json.dumps({'message': '本次回答耗时过长，请稍后重试或缩短问题后再试'}, ensure_ascii=False)}\n\n"
        return
    except Exception:
        logger.exception("chat generation failed")
        yield f"event: error\ndata: {json.dumps({'message': '模型服务暂不可用，请稍后重试'}, ensure_ascii=False)}\n\n"
        return

    try:
        answer = result.get("answer", {})
        content = answer.get("content", "") if isinstance(answer, dict) else str(answer)
        citations = answer.get("citations", []) if isinstance(answer, dict) else []
        confidence = result.get("confidence", 0.0)
        warnings = list(result.get("warnings", []) or [])

        # node_update: 检索完成
        yield f"event: node_update\ndata: {json.dumps({'node': 'retrieve', 'status': 'completed', 'message': f'检索到 {len(citations)} 条相关文档'}, ensure_ascii=False)}\n\n"

        # 无模型片段的 mock、拒答和确定性回答仍发送一次完整内容。
        if not streamed_tokens:
            yield f"event: token\ndata: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"

        # citation
        for cit in citations:
            yield f"event: citation\ndata: {json.dumps(cit, ensure_ascii=False)}\n\n"

        # 会话留痕不应影响已经生成的回答。否则持久化异常会让 SSE 无 final 事件，
        # 前端只能一直停留在“正在检索”。
        try:
            assistant_message_id = uuid4()
            msg = Message(
                id=assistant_message_id,
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
            answer_persisted = True
        except Exception:
            answer_persisted = False
            logger.exception("chat answer persistence failed")
            try:
                await db.rollback()
            except Exception:
                logger.exception("chat answer persistence rollback failed")
            warnings.append("本次回答未能写入会话历史，请稍后重试")

        final = {
            "content": content,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings,
        }
        yield f"event: final\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"

        # StreamingResponse resumes the generator after sending the final chunk,
        # then executes its BackgroundTasks after normal iteration completes.
        if (
            answer_persisted
            and not injection_rejected
            and background_tasks is not None
            and user_id is not None
            and latest_user_message_id is not None
        ):
            try:
                background_tasks.add_task(
                    memory_maintenance.refresh_memory_state,
                    conversation_id,
                    user_id,
                    latest_user_message_id,
                    assistant_message_id,
                )
            except Exception as exc:
                logger.error(
                    "memory maintenance scheduling failed conversation_id=%s user_id=%s "
                    "user_message_id=%s assistant_message_id=%s error_type=%s",
                    conversation_id,
                    user_id,
                    latest_user_message_id,
                    assistant_message_id,
                    type(exc).__name__,
                )
    except Exception:
        logger.exception("chat response finalization failed")
        yield f"event: error\ndata: {json.dumps({'message': '回答已生成但传输失败，请稍后重试'}, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
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
    user_message_id = uuid4()
    user_msg = Message(
        id=user_message_id,
        conversation_id=conversation_id,
        role="user",
        content=request.message,
    )
    db.add(user_msg)
    await db.commit()

    thread_id = uuid4()
    knowledge_context = {
        "id": request.knowledge_node_id,
        "name": request.knowledge_node_name,
    }

    return StreamingResponse(
        _stream_answer(
            db=db,
            thread_id=thread_id,
            query=request.message,
            conversation_id=conversation_id,
            intent=request.intent or "policy",
            knowledge_context=knowledge_context if any(knowledge_context.values()) else None,
            user_id=user.id,
            user_preferences=user.preferences,
            latest_user_message_id=user_message_id,
            background_tasks=background_tasks,
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
