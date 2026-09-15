import asyncio
import json
import unittest


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _MemoryClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.requests = []

    async def get(self, path, *, headers):
        self.requests.append((path, headers))
        return _Response(self.pages.pop(0))


class MemoryVerificationTests(unittest.IsolatedAsyncioTestCase):
    def test_final_sse_content_parses_frames_and_normalizes_recall(self):
        from scripts.verify_memory_system import (
            assert_recall_preferences,
            final_sse_content,
        )

        body = (
            ": heartbeat\r\n\r\n"
            "event: token\r\n"
            f"data: {json.dumps({'content': 'partial'}, ensure_ascii=False)}\r\n\r\n"
            "event: final\r\n"
            f"data: {json.dumps({'content': '我记得你偏好仙 林校区，\\n并希望下 午上课。'}, ensure_ascii=False)}\r\n\r\n"
        )

        content = final_sse_content(body)
        assert_recall_preferences(content)

    def test_final_sse_content_reports_error_without_echoing_private_payload(self):
        from scripts.verify_memory_system import final_sse_content

        private_text = "用户完整记忆不应进入日志"
        body = (
            "event: error\n"
            f"data: {json.dumps({'message': private_text}, ensure_ascii=False)}\n\n"
        )

        with self.assertRaises(AssertionError) as caught:
            final_sse_content(body)

        self.assertNotIn(private_text, str(caught.exception))

    async def test_wait_for_memory_stops_at_configured_poll_boundary(self):
        from scripts.verify_memory_system import wait_for_memory

        client = _MemoryClient([
            {"items": [], "next_cursor": None},
            {"items": [], "next_cursor": None},
            {"items": [], "next_cursor": None},
        ])
        sleeps = []

        async def record_sleep(seconds):
            sleeps.append(seconds)

        with self.assertRaises(AssertionError):
            await wait_for_memory(
                client,
                {"Authorization": "redacted"},
                "仙林校区",
                max_attempts=3,
                delay_seconds=0.25,
                sleep=record_sleep,
            )

        self.assertEqual(len(client.requests), 3)
        self.assertEqual(sleeps, [0.25, 0.25])

    async def test_wait_for_memory_returns_matching_item_before_limit(self):
        from scripts.verify_memory_system import wait_for_memory

        expected = {"id": "memory-1", "content": "长期偏好仙林校区下午课程"}
        client = _MemoryClient([
            {"items": [], "next_cursor": None},
            {"items": [expected], "next_cursor": None},
        ])

        async def no_wait(_seconds):
            return None

        actual = await wait_for_memory(
            client,
            {"Authorization": "redacted"},
            "仙林校区",
            max_attempts=4,
            delay_seconds=0,
            sleep=no_wait,
        )

        self.assertEqual(actual, expected)
        self.assertEqual(len(client.requests), 2)

    async def test_temporary_user_cleanup_runs_when_probe_fails(self):
        from scripts.verify_memory_system import run_with_temporary_user

        cleaned = []

        async def failing_probe(username):
            raise RuntimeError(f"probe failed for {username}")

        async def cleanup(username):
            cleaned.append(username)

        with self.assertRaises(RuntimeError):
            await run_with_temporary_user("memorycheck-test", failing_probe, cleanup)

        self.assertEqual(cleaned, ["memorycheck-test"])

    def test_recall_prompt_uses_the_observable_ruling(self):
        from scripts.verify_memory_system import RECALL_PROMPT

        self.assertEqual(RECALL_PROMPT, "请明确复述你记得的校区和时间偏好")


if __name__ == "__main__":
    unittest.main()
