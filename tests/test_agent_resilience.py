import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from apps.api.routes.chat import _stream_answer, invoke_graph_with_timeout
from fastapi import BackgroundTasks
from services.agent_runtime.policy_agent import PolicyAgent
from services.rag.retrieval import build_context


class _NeverCalledLlm:
    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        raise AssertionError("政策证据校验不应再发起第二次模型调用")


class _SlowGraph:
    async def ainvoke(self, _state, _config):
        await asyncio.sleep(0.02)
        return {}


class _FailingPersistenceDb:
    def __init__(self):
        self.rollback_count = 0

    def add(self, _item):
        pass

    async def execute(self, _statement):
        return None

    async def commit(self):
        raise RuntimeError("database unavailable")

    async def rollback(self):
        self.rollback_count += 1


class AgentResilienceTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_policy_evidence_verification_is_deterministic(self) -> None:
        llm = _NeverCalledLlm()
        agent = PolicyAgent(db=object(), llm=llm)
        state = {
            "answer": {"content": "依据培养方案，达到要求后可以申请。"},
            "evidence": [{"content": "培养方案规定的申请条件。"}],
            "confidence": 0.9,
            "warnings": [],
        }

        result = asyncio.run(agent.verify(state))

        self.assertEqual(llm.calls, 0)
        self.assertEqual(result["confidence"], 0.9)

    def test_external_chat_model_preserves_configured_thinking_mode(self) -> None:
        source = (self.ROOT / "services/agent_runtime/llm.py").read_text(encoding="utf-8")

        self.assertIn('extra_body={"enable_thinking": settings.llm_enable_thinking}', source)

    def test_agent_invocation_has_a_total_timeout(self) -> None:
        with patch("apps.api.routes.chat.settings.agent_response_timeout_seconds", 0.001):
            with self.assertRaises(asyncio.TimeoutError):
                asyncio.run(invoke_graph_with_timeout(_SlowGraph(), {}, {}))

    def test_mock_summary_never_calls_external_model(self) -> None:
        from services.memory.summarizer import generate_conversation_summary
        from tests.test_conversation_memory import make_snapshots

        with patch("services.memory.summarizer.create_chat_model", side_effect=AssertionError("external model")):
            with patch("services.memory.summarizer.settings.mock_llm", True):
                result = asyncio.run(generate_conversation_summary(
                    "目标：新闻辅修", make_snapshots([("user", "大二开始"), ("assistant", "先核对课程")]),
                ))
        self.assertIn("新闻辅修", result)
        self.assertIn("大二", result)

    def test_policy_context_is_bounded_before_model_generation(self) -> None:
        chunks = [{
            "document_title": "测试政策",
            "content": "政策原文" * 2_000,
        } for _ in range(4)]

        context = build_context(chunks, max_tokens=100)

        # 中文通常接近一字一 token；这里使用两倍字符预算，既保留来源标签，
        # 又避免多份长文档被整体塞入一次模型请求。
        self.assertLessEqual(len(context), 200)
        self.assertIn("【来源1】测试政策", context)

    def test_chat_finalizes_without_scheduling_when_history_persistence_fails(self) -> None:
        background = BackgroundTasks()
        db = _FailingPersistenceDb()

        async def collect_events():
            return [event async for event in _stream_answer(
                db=db,
                thread_id=uuid4(),
                query="请记住我偏好下午上课",
                conversation_id=uuid4(),
                user_id=uuid4(),
                latest_user_message_id=uuid4(),
                background_tasks=background,
            )]

        with (
            patch("apps.api.routes.chat.settings.mock_llm", True),
            patch("apps.api.routes.chat.detect_injection", return_value=False),
            self.assertLogs("fuxiaohe.chat", level="ERROR"),
        ):
            events = asyncio.run(collect_events())

        final = json.loads(
            next(event for event in events if event.startswith("event: final")).split("data: ", 1)[1]
        )
        self.assertIn("未能写入会话历史", final["warnings"][-1])
        self.assertEqual(db.rollback_count, 1)
        self.assertEqual(len(background.tasks), 0)

    def test_frontend_exposes_stream_failure_and_recovers_stale_route_assets(self) -> None:
        chat = (self.ROOT / "apps/web/src/views/ChatView.vue").read_text(encoding="utf-8")
        client = (self.ROOT / "apps/web/src/api/client.ts").read_text(encoding="utf-8")
        store = (self.ROOT / "apps/web/src/stores/chat.ts").read_text(encoding="utf-8")
        app = (self.ROOT / "apps/web/src/App.vue").read_text(encoding="utf-8")
        nginx = (self.ROOT / "infra/nginx/fuxiaohe.conf").read_text(encoding="utf-8")

        self.assertIn("store.error", chat)
        self.assertIn("重试", chat)
        self.assertIn("receivedError = true", client)
        self.assertIn("!receivedFinal && !receivedError", client)
        self.assertIn("CLIENT_STREAM_TIMEOUT_MS", client)
        self.assertIn("controller.abort()", client)
        self.assertIn("function createMessageId()", store)
        self.assertIn("globalThis.crypto?.randomUUID", store)
        self.assertIn("local-", store)
        self.assertIn("if (streaming.value) return", store)
        self.assertIn("vite:preloadError", app)
        self.assertIn("location ^~ /assets/", nginx)
        self.assertIn("try_files $uri =404", nginx)
        self.assertIn('Cache-Control "no-cache', nginx)

    def test_policy_source_manifest_keeps_current_and_archived_versions_distinct(self) -> None:
        source = (self.ROOT / "scripts/import_policy_sources.py").read_text(encoding="utf-8")

        self.assertIn("南京大学2025版学生手册（本科生部分）", source)
        self.assertIn("南京大学关于本科毕业论文（设计）工作的若干规定（2019年8月修订）", source)
        self.assertIn("南京大学2024学生手册（本科生部分）", source)
        self.assertIn('"is_active": False', source)
        self.assertIn("PyMuPDF", (self.ROOT / "requirements.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
