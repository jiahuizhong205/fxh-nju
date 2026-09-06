"""针对运行中的 API 执行完整新用户主流程验收，并清理临时账号。"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import secrets

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.models import User


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def require(response: httpx.Response, expected: int, step: str) -> dict:
    if response.status_code != expected:
        raise AssertionError(f"{step}失败：HTTP {response.status_code} {response.text[:500]}")
    if not response.content:
        return {}
    return response.json()


async def cleanup(username: str) -> None:
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(delete(User).where(User.username == username))
        await db.commit()
    await engine.dispose()


async def verify(base_url: str) -> list[str]:
    username = f"accept{secrets.token_hex(5)}"
    password = "Garden2026"
    completed: list[str] = []
    await cleanup(username)
    try:
        # 本机验收不应继承系统代理；否则 localhost 可能被代理服务错误转发。
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=30, trust_env=False
        ) as client:
            readiness = require(await client.get("/api/readiness"), 200, "就绪检查")
            assert readiness["knowledge"]["active_documents"] >= 2
            completed.append("服务与知识库就绪")

            auth = require(await client.post("/api/v1/auth/register", json={
                "username": username, "password": password, "nickname": "验收种子",
            }), 200, "注册")
            assert auth["user"]["onboarding_completed"] is False
            headers = {"Authorization": f"Bearer {auth['token']}"}
            completed.append("注册并进入待引导状态")

            options = require(await client.get("/api/v1/profile/options", headers=headers), 200, "画像选项")
            programs = require(await client.get("/api/v1/programs"), 200, "专业目录")["programs"]
            assert len(programs) >= 70 and any(p["name"] == "汉语言文学" for p in programs)
            assert options["interests"] and options["strengths"]
            completed.append("加载真实专业目录与画像选项")

            profile = require(await client.put("/api/v1/profile", headers=headers, json={
                "major": "汉语言文学", "grade": "大一", "campus": "仙林校区",
                "interests": options["interests"][:2], "strengths": options["strengths"][:2],
                "career_goals": "跨学科学习与内容研究", "math_willingness": True,
                "campus_flexibility": True, "credit_budget": 50,
                "certificate_goal": "degree", "schedule_preferences": {},
            }), 200, "保存画像")["profile"]
            assert profile["major"] == "汉语言文学"
            completed.append("保存个人画像")

            upload = require(await client.post(
                "/api/v1/profile/avatar", headers=headers,
                files={"file": ("avatar.png", PNG_1X1, "image/png")},
            ), 200, "上传头像")
            assert upload["avatar"]["size_bytes"] == len(PNG_1X1)
            avatar = await client.get("/api/v1/profile/avatar", headers=headers)
            assert avatar.status_code == 200 and avatar.content == PNG_1X1
            completed.append("上传并重新读取头像")

            onboarding = require(await client.put(
                "/api/v1/auth/onboarding", headers=headers, json={"completed": True},
            ), 200, "完成引导")
            assert onboarding["onboarding_completed"] is True
            me = require(await client.get("/api/v1/auth/me", headers=headers), 200, "读取账号")["user"]
            assert me["onboarding_completed"] is True
            completed.append("完成引导并进入首页状态")

            recommendations = require(await client.post(
                "/api/v1/recommend", headers=headers, json={},
            ), 200, "专业推荐")["recommendations"]
            assert recommendations and all("participant_count" in item["program"] for item in recommendations)
            completed.append("生成数据库驱动的专业推荐")

            plan = require(await client.get(
                "/api/v1/programs/plan", headers=headers, params={"program": "汉语言文学"},
            ), 200, "课程规划")
            assert plan["items"] and any(item.get("source_url") for item in plan["items"])
            completed.append("读取官方课程并生成规划")

            search = require(await client.get(
                "/api/v1/knowledge/search", headers=headers, params={"q": "辅修学分"},
            ), 200, "政策检索")
            assert search["results"] and any(citation.get("source_url") for citation in search["citations"])
            completed.append("检索带官方来源的政策证据")

            chat = await client.post(
                "/api/v1/chat", headers=headers,
                json={"message": "辅修达到多少学分可以申请结业证明？", "intent": "policy"},
            )
            assert chat.status_code == 200 and "event: final" in chat.text
            final_lines = [line[6:] for line in chat.text.splitlines() if line.startswith("data: ")]
            assert any(json.loads(line).get("content") for line in final_lines)
            completed.append("完成政策问答 SSE 流程")

            conversations = require(await client.get(
                "/api/v1/conversations", headers=headers,
            ), 200, "会话历史")
            assert conversations
            messages = require(await client.get(
                f"/api/v1/conversations/{conversations[0]['id']}/messages", headers=headers,
            ), 200, "会话消息")
            assert len(messages) >= 2
            completed.append("保存并读取问答历史")

            progress = require(await client.get(
                "/api/v1/learning/progress", headers=headers,
            ), 200, "学习进度")
            assert progress["completed_credits"] == 0 and progress["learning_days"] == 0
            completed.append("新用户学习进度为空且无占位值")
    finally:
        await cleanup(username)
    return completed


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    completed = await verify(args.base_url)
    for index, step in enumerate(completed, start=1):
        print(f"{index:02d}. PASS {step}")
    print(f"新用户主流程验收通过：{len(completed)} 个检查点")


if __name__ == "__main__":
    asyncio.run(main())
