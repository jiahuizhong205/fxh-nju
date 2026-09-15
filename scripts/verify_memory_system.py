"""Opt-in real-provider smoke test for summaries and long-term memory."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import json
from pathlib import Path
import secrets
import sys
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from apps.api.config import settings
from apps.api.models import Conversation, ConversationSummary, User


RECALL_PROMPT = "请明确复述你记得的校区和时间偏好"
_TEMPORARY_PASSWORD = "Garden2026"
_AUTOMATIC_MEMORY_PHRASE = "仙林"


def _response_json(response: httpx.Response, step: str, expected_status: int = 200) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise AssertionError(f"{step}失败：HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError:
        raise AssertionError(f"{step}失败：响应不是 JSON") from None
    if not isinstance(payload, dict):
        raise AssertionError(f"{step}失败：响应结构不正确")
    return payload


def _sse_events(sse_body: str):
    """Yield parsed SSE frames without exposing event payloads in errors."""
    event_name = "message"
    data_lines: list[str] = []
    normalized = sse_body.replace("\r\n", "\n").replace("\r", "\n")
    for line in (*normalized.split("\n"), ""):
        if line == "":
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)


def final_sse_content(sse_body: str) -> str:
    """Return the final chat content while keeping provider/user text out of errors."""
    for event_name, raw_data in _sse_events(sse_body):
        if event_name == "error":
            raise AssertionError("聊天返回 error SSE 事件")
        if event_name != "final":
            continue
        try:
            payload = json.loads(raw_data)
        except (TypeError, json.JSONDecodeError):
            raise AssertionError("聊天 final SSE 数据不是有效 JSON") from None
        content = payload.get("content", "") if isinstance(payload, dict) else ""
        if isinstance(content, str) and content.strip() and "模型服务暂不可用" not in content:
            return content.strip()
        raise AssertionError("聊天 final SSE 未包含有效内容")
    raise AssertionError("聊天响应缺少 final SSE 事件")


def assert_recall_preferences(content: str) -> None:
    normalized = "".join(content.split())
    if "仙林" not in normalized or "下午" not in normalized:
        raise AssertionError("新会话未同时复述校区和时间偏好")


async def wait_for_memory(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    phrase: str,
    *,
    max_attempts: int = 9,
    delay_seconds: float = 5.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, Any]:
    """Poll a bounded number of times for an automatically captured memory."""
    attempts = max(1, int(max_attempts))
    for attempt in range(attempts):
        response = await client.get("/api/v1/memories?limit=50", headers=headers)
        payload = _response_json(response, "轮询自动记忆")
        items = payload.get("items")
        if not isinstance(items, list):
            raise AssertionError("轮询自动记忆失败：响应缺少 items")
        for item in items:
            if isinstance(item, dict) and phrase in str(item.get("content", "")):
                return item
        if attempt + 1 < attempts:
            await sleep(delay_seconds)
    raise AssertionError("限定时间内未生成预期的自动记忆")


async def _summary_exists(
    db: AsyncSession,
    conversation_id: UUID,
    username: str,
) -> bool:
    result = await db.execute(
        select(ConversationSummary)
        .join(Conversation, Conversation.id == ConversationSummary.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .where(
            ConversationSummary.conversation_id == conversation_id,
            User.username == username,
        )
    )
    row = result.scalar_one_or_none()
    return bool(
        row is not None
        and str(row.summary or "").strip()
        and row.summarized_through_message_id is not None
    )


async def assert_summary_cursor_advanced(
    conversation_id: str,
    username: str,
    *,
    max_attempts: int = 9,
    delay_seconds: float = 5.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Require a non-empty owned summary and an advanced message cursor."""
    parsed_id = UUID(conversation_id)
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        attempts = max(1, int(max_attempts))
        for attempt in range(attempts):
            async with factory() as db:
                if await _summary_exists(db, parsed_id, username):
                    return
            if attempt + 1 < attempts:
                await sleep(delay_seconds)
    finally:
        await engine.dispose()
    raise AssertionError("限定时间内对话摘要未生成或游标未推进")


async def cleanup_test_user(username: str) -> None:
    """Hard-delete the temporary user; database cascades remove all owned data."""
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            await db.execute(delete(User).where(User.username == username))
            await db.commit()
    finally:
        await engine.dispose()


async def run_with_temporary_user(
    username: str,
    probe: Callable[[str], Awaitable[None]],
    cleanup: Callable[[str], Awaitable[None]],
) -> None:
    """Guarantee cleanup even when registration or any later assertion fails."""
    try:
        await probe(username)
    finally:
        await cleanup(username)


async def _chat(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    message: str,
    intent: str,
    thread_id: str | None = None,
) -> tuple[str, str]:
    payload: dict[str, Any] = {"message": message, "intent": intent}
    if thread_id is not None:
        payload["thread_id"] = thread_id
    response = await client.post("/api/v1/chat", headers=headers, json=payload)
    if response.status_code != 200:
        raise AssertionError(f"聊天失败：HTTP {response.status_code}")
    conversation_id = response.headers.get("X-Conversation-Id", "").strip()
    if not conversation_id:
        raise AssertionError("聊天响应缺少 X-Conversation-Id")
    return conversation_id, final_sse_content(response.text)


async def _verify_memory_crud(client: httpx.AsyncClient, headers: dict[str, str]) -> None:
    created = _response_json(
        await client.post("/api/v1/memories", headers=headers, json={
            "category": "study_constraint",
            "content": "我偏好在图书馆安静区域学习",
            "importance": 0.6,
        }),
        "创建手动记忆",
        201,
    )
    memory_id = str(created.get("id", ""))
    if not memory_id:
        raise AssertionError("创建手动记忆失败：响应缺少 id")
    fetched = _response_json(
        await client.get(f"/api/v1/memories/{memory_id}", headers=headers),
        "读取手动记忆",
    )
    if fetched.get("id") != created.get("id"):
        raise AssertionError("读取手动记忆返回了错误记录")
    updated = _response_json(
        await client.patch(f"/api/v1/memories/{memory_id}", headers=headers, json={
            "content": "我长期偏好在图书馆安静区域学习",
            "importance": 0.8,
        }),
        "更新手动记忆",
    )
    if updated.get("importance") != 0.8:
        raise AssertionError("更新手动记忆未生效")
    deleted = await client.delete(f"/api/v1/memories/{memory_id}", headers=headers)
    if deleted.status_code != 204:
        raise AssertionError(f"删除手动记忆失败：HTTP {deleted.status_code}")


async def _probe_user(username: str, base_url: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=180, trust_env=False) as client:
        readiness = _response_json(await client.get("/api/readiness"), "就绪检查")
        knowledge = readiness.get("knowledge")
        if (
            readiness.get("status") != "ready"
            or not isinstance(knowledge, dict)
            or knowledge.get("indexed_for_current_provider") != knowledge.get("chunks")
        ):
            raise AssertionError("真实模型、向量或知识库尚未就绪")

        auth = _response_json(await client.post("/api/v1/auth/register", json={
            "username": username,
            "password": _TEMPORARY_PASSWORD,
            "nickname": "记忆验收",
        }), "注册")
        token = auth.get("token")
        if not isinstance(token, str) or not token:
            raise AssertionError("注册响应缺少 token")
        headers = {"Authorization": f"Bearer {token}"}

        await _verify_memory_crud(client, headers)
        print("PASS memory CRUD")

        conversation_id: str | None = None
        detail = "这是用于触发摘要边界的非敏感重复说明，不包含额外个人信息。" * 250
        for index in range(7):
            conversation_id, _content = await _chat(
                client,
                headers,
                message=(
                    f"第 {index + 1} 轮。请记住：我长期偏好仙林校区的下午课程。"
                    f"{detail}"
                ),
                intent="schedule",
                thread_id=conversation_id,
            )
        if conversation_id is None:
            raise AssertionError("未创建验收会话")

        await wait_for_memory(client, headers, _AUTOMATIC_MEMORY_PHRASE)
        print("PASS automatic memory capture")
        await assert_summary_cursor_advanced(conversation_id, username)
        print("PASS summary and cursor")

        new_conversation_id, recalled = await _chat(
            client,
            headers,
            message=RECALL_PROMPT,
            intent="schedule",
        )
        if new_conversation_id == conversation_id:
            raise AssertionError("跨会话召回未创建新会话")
        assert_recall_preferences(recalled)
        print("PASS cross-conversation recall")


async def verify(base_url: str = "http://127.0.0.1:8000") -> None:
    if settings.mock_llm:
        raise RuntimeError("请先设置 MOCK_LLM=false")
    required = (
        (settings.llm_base_url, "LLM_BASE_URL"),
        (settings.llm_api_key, "LLM_API_KEY"),
        (settings.llm_model, "LLM_MODEL"),
        (settings.embedding_base_url, "EMBEDDING_BASE_URL"),
        (settings.embedding_api_key, "EMBEDDING_API_KEY"),
        (settings.embedding_api_model, "EMBEDDING_API_MODEL"),
    )
    missing = [name for value, name in required if not str(value).strip()]
    if missing:
        raise RuntimeError("真实 smoke 配置不完整：" + ", ".join(missing))

    username = f"memorycheck{secrets.token_hex(5)}"

    async def probe(value: str) -> None:
        await _probe_user(value, base_url.rstrip("/"))

    await run_with_temporary_user(username, probe, cleanup_test_user)
    print("PASS temporary data cleanup")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    asyncio.run(verify(arguments.base_url))
