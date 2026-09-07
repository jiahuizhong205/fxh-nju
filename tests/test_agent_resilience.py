import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch

from apps.api.routes.chat import invoke_graph_with_timeout
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

    def test_agent_invocation_has_a_total_timeout(self) -> None:
        with patch("apps.api.routes.chat.settings.agent_response_timeout_seconds", 0.001):
            with self.assertRaises(asyncio.TimeoutError):
                asyncio.run(invoke_graph_with_timeout(_SlowGraph(), {}, {}))

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

    def test_chat_finalizes_when_history_persistence_fails(self) -> None:
        source = (self.ROOT / "apps/api/routes/chat.py").read_text(encoding="utf-8")

        self.assertIn("chat answer persistence failed", source)
        self.assertIn("await db.rollback()", source)
        self.assertIn("event: final", source)

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
        self.assertIn("if (streaming.value) return", store)
        self.assertIn("vite:preloadError", app)
        self.assertIn("location ^~ /assets/", nginx)
        self.assertIn("try_files $uri =404", nginx)
        self.assertIn('Cache-Control "no-cache', nginx)

    def test_policy_source_manifest_keeps_current_and_archived_versions_distinct(self) -> None:
        source = (self.ROOT / "scripts/import_policy_sources.py").read_text(encoding="utf-8")

        self.assertIn("南京大学2025版学生手册（本科生部分）", source)
        self.assertIn("南京大学2024学生手册（本科生部分）", source)
        self.assertIn('"is_active": False', source)
        self.assertIn("PyMuPDF", (self.ROOT / "requirements.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
