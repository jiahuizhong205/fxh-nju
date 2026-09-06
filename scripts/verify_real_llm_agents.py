"""以临时账号验证五条真实 LLM 智能体链路，并清理验收数据。"""

from __future__ import annotations

import asyncio
import argparse
import json
import secrets

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.models import Job, User


async def cleanup(username: str, job_id: str) -> None:
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(Job).where(Job.id == job_id))
        await db.execute(delete(User).where(User.username == username))
        await db.commit()
    await engine.dispose()


def response_json(response: httpx.Response, step: str) -> dict:
    if response.status_code != 200:
        raise AssertionError(f"{step}失败：HTTP {response.status_code}")
    return response.json()


def final_content(sse_body: str, intent: str) -> str:
    if "event: error" in sse_body:
        raise AssertionError(f"{intent} 智能体返回错误事件")
    lines = sse_body.splitlines()
    for index, line in enumerate(lines):
        if line == "event: final" and index + 1 < len(lines) and lines[index + 1].startswith("data: "):
            content = json.loads(lines[index + 1][6:]).get("content", "").strip()
            if content and "模型服务暂不可用" not in content:
                return content
    raise AssertionError(f"{intent} 智能体未返回有效最终内容")


async def insert_test_job(job_id: str) -> None:
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(Job(
            id=job_id, employer="LLM 验收临时岗位", title="内容研究实习生", location="南京",
            majors=["汉语言文学"], preferred_cross=["新闻学"],
            skills_required=["写作", "研究"], skills_preferred=["数据分析"],
            deadline="2099-12-31", source="automated-agent-check", source_url="",
            data_status="test", is_active=True,
        ))
        await db.commit()
    await engine.dispose()


async def verify(intent_filter: str = "") -> None:
    if settings.mock_llm:
        raise RuntimeError("请先设置 MOCK_LLM=false")

    username = f"agentcheck{secrets.token_hex(5)}"
    job_id = f"agent-check-{secrets.token_hex(5)}"
    await cleanup(username, job_id)
    try:
        # 真实模型首个请求偶尔需要较长的冷启动时间；验收时完整读取 SSE，
        # 防止客户端提前断开而影响服务端写入会话记录。
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=180, trust_env=False) as client:
            readiness = response_json(await client.get("/api/readiness"), "就绪检查")
            if readiness["status"] != "ready" or readiness["knowledge"]["indexed_for_current_provider"] != readiness["knowledge"]["chunks"]:
                raise AssertionError("真实模型或知识库尚未就绪")

            auth = response_json(await client.post("/api/v1/auth/register", json={
                "username": username, "password": "Garden2026", "nickname": "智能体验收",
            }), "注册")
            headers = {"Authorization": f"Bearer {auth['token']}"}
            options = response_json(await client.get("/api/v1/profile/options", headers=headers), "画像选项")
            response_json(await client.put("/api/v1/profile", headers=headers, json={
                "major": "汉语言文学", "grade": "大一", "campus": "仙林校区",
                "interests": options["interests"][:2], "strengths": options["strengths"][:2],
                "career_goals": "内容研究与科技传播", "math_willingness": True,
                "campus_flexibility": True, "credit_budget": 50,
                "certificate_goal": "degree", "schedule_preferences": {},
            }), "保存画像")
            await insert_test_job(job_id)

            checks = [
                ("policy", "辅修达到多少学分可以申请结业证明？"),
                ("recommend", "请结合我的画像推荐适合的辅修方向。"),
                ("schedule", "请为汉语言文学制定课程规划。"),
                ("tutor", "请用通俗方式讲解新闻采访的基本知识。"),
                ("career", "我主修汉语言文学并考虑新闻学，想了解适合的实习岗位。"),
            ]
            if intent_filter:
                checks = [item for item in checks if item[0] == intent_filter]
            for intent, message in checks:
                result = await client.post("/api/v1/chat", headers=headers, json={
                    "message": message, "intent": intent,
                })
                content = final_content(result.text, intent)
                print(f"PASS {intent}: {len(content)} chars")
    finally:
        await cleanup(username, job_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", choices=("policy", "recommend", "schedule", "tutor", "career"))
    args = parser.parse_args()
    asyncio.run(verify(args.intent or ""))
