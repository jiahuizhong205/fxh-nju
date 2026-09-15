import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services.memory import maintenance


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _MaintenanceDb:
    def __init__(self, responses, events):
        self.responses = list(responses)
        self.events = events
        self.statements = []

    async def execute(self, statement):
        self.events.append("query")
        self.statements.append(statement)
        return _ScalarResult(self.responses.pop(0))

    async def rollback(self):
        self.events.append("rollback")


class _SessionContext:
    def __init__(self, db, events):
        self.db = db
        self.events = events

    async def __aenter__(self):
        self.events.append("session")
        return self.db

    async def __aexit__(self, *_args):
        self.events.append("session_closed")


class MemoryMaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_capture_uses_fresh_session_and_committed_message_ids(self):
        conversation_id = uuid4()
        user_id = uuid4()
        user_message_id = uuid4()
        assistant_message_id = uuid4()
        events = []
        user_message = SimpleNamespace(
            id=user_message_id,
            role="user",
            content="请记住我偏好下午上课",
        )
        assistant_message = SimpleNamespace(
            id=assistant_message_id,
            role="assistant",
            content="好的，我会记住。",
        )
        db = _MaintenanceDb([
            conversation_id,
            {"memory": {"auto_capture_enabled": True}},
            user_message,
            assistant_message,
            {"memory": {"auto_capture_enabled": True}},
        ], events)
        candidate = SimpleNamespace(canonical_key="schedule:afternoon")

        async def refresh_summary(received_conversation_id):
            events.append("summary")
            self.assertEqual(received_conversation_id, conversation_id)
            return SimpleNamespace(updated=True, summarized_message_count=4)

        async def extract(latest_user_text, *, assistant_message=""):
            events.append("extract")
            self.assertEqual(latest_user_text, user_message.content)
            self.assertEqual(assistant_message, assistant_message_obj.content)
            return [candidate]

        assistant_message_obj = assistant_message
        async def upsert_result(*_args, **_kwargs):
            events.append("upsert")
            return 1

        upsert = AsyncMock(side_effect=upsert_result)

        with (
            patch("services.memory.maintenance.async_session", return_value=_SessionContext(db, events)) as sessions,
            patch("services.memory.maintenance.refresh_conversation_summary", side_effect=refresh_summary),
            patch("services.memory.maintenance.extract_memory_candidates", side_effect=extract),
            patch("services.memory.maintenance.upsert_memory_candidates", upsert),
        ):
            result = await maintenance._refresh_memory_state(
                conversation_id,
                user_id,
                user_message_id,
                assistant_message_id,
            )

        sessions.assert_called_once_with()
        self.assertEqual(events[0], "summary")
        self.assertLess(events.index("summary"), events.index("session"))
        self.assertLess(events.index("session"), events.index("extract"))
        self.assertLess(events.index("extract"), events.index("upsert"))
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.upserted_count, 1)
        upsert.assert_awaited_once_with(
            db,
            user_id,
            [candidate],
            conversation_id,
            user_message_id,
        )
        statement_text = "\n".join(str(statement) for statement in db.statements)
        statement_parameters = {
            value
            for statement in db.statements
            for value in statement.compile().params.values()
        }
        self.assertIn("conversations.user_id", statement_text)
        self.assertIn(user_id, statement_parameters)
        self.assertIn(user_message_id, statement_parameters)
        self.assertIn(assistant_message_id, statement_parameters)

    async def test_capture_disabled_during_extraction_abandons_write_after_locked_recheck(self):
        conversation_id = uuid4()
        user_id = uuid4()
        user_message_id = uuid4()
        assistant_message_id = uuid4()
        events = []
        db = _MaintenanceDb([
            conversation_id,
            {"memory": {"auto_capture_enabled": True}},
            SimpleNamespace(
                id=user_message_id,
                role="user",
                content="请记住我偏好下午上课",
            ),
            SimpleNamespace(
                id=assistant_message_id,
                role="assistant",
                content="好的。",
            ),
            {"memory": {"auto_capture_enabled": False}},
        ], events)
        candidate = SimpleNamespace(canonical_key="schedule:afternoon")

        async def extract(*_args, **_kwargs):
            events.append("extract")
            return [candidate]

        with (
            patch(
                "services.memory.maintenance.async_session",
                return_value=_SessionContext(db, events),
            ),
            patch(
                "services.memory.maintenance.refresh_conversation_summary",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(updated=True, summarized_message_count=2),
            ) as refresh_summary,
            patch(
                "services.memory.maintenance.extract_memory_candidates",
                side_effect=extract,
            ),
            patch(
                "services.memory.maintenance.upsert_memory_candidates",
                new_callable=AsyncMock,
            ) as upsert,
        ):
            result = await maintenance._refresh_memory_state(
                conversation_id,
                user_id,
                user_message_id,
                assistant_message_id,
            )

        refresh_summary.assert_awaited_once_with(conversation_id)
        upsert.assert_not_awaited()
        self.assertTrue(result.summary_updated)
        self.assertEqual(result.summarized_message_count, 2)
        self.assertFalse(result.auto_capture_enabled)
        self.assertEqual(result.candidate_count, 1)
        self.assertEqual(result.upserted_count, 0)
        extraction_index = events.index("extract")
        self.assertIn("rollback", events[:extraction_index])
        self.assertIn("query", events[extraction_index + 1:])
        self.assertIn("FOR UPDATE", str(db.statements[-1]))

    async def test_disabled_capture_still_refreshes_summary_but_skips_extraction(self):
        conversation_id = uuid4()
        user_id = uuid4()
        events = []
        db = _MaintenanceDb([
            conversation_id,
            {"memory": {"auto_capture_enabled": False}},
        ], events)
        async def refresh_summary_result(*_args, **_kwargs):
            events.append("summary")
            return SimpleNamespace(updated=False, summarized_message_count=0)

        refresh_summary = AsyncMock(side_effect=refresh_summary_result)

        with (
            patch("services.memory.maintenance.async_session", return_value=_SessionContext(db, events)),
            patch("services.memory.maintenance.refresh_conversation_summary", refresh_summary),
            patch("services.memory.maintenance.extract_memory_candidates", new_callable=AsyncMock) as extract,
            patch("services.memory.maintenance.upsert_memory_candidates", new_callable=AsyncMock) as upsert,
        ):
            await maintenance._refresh_memory_state(
                conversation_id,
                user_id,
                uuid4(),
                uuid4(),
            )

        refresh_summary.assert_awaited_once_with(conversation_id)
        extract.assert_not_awaited()
        upsert.assert_not_awaited()
        self.assertEqual(events[0], "summary")

    async def test_timeout_is_bounded_and_does_not_escape_background_boundary(self):
        cancelled = asyncio.Event()

        async def never_finishes(*_args):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with (
            patch("services.memory.maintenance._refresh_memory_state", side_effect=never_finishes),
            patch("services.memory.maintenance.settings.memory_background_timeout_seconds", 0.001),
            self.assertLogs("fuxiaohe.memory.maintenance", level="WARNING") as captured,
        ):
            await maintenance.refresh_memory_state(uuid4(), uuid4(), uuid4(), uuid4())

        self.assertTrue(cancelled.is_set())
        self.assertTrue(any("timed out" in line for line in captured.output))

    async def test_failure_is_logged_without_escaping_background_boundary(self):
        secret = "sk-must-not-appear-in-logs"
        with (
            patch(
                "services.memory.maintenance._refresh_memory_state",
                side_effect=RuntimeError(secret),
            ),
            self.assertLogs("fuxiaohe.memory.maintenance", level="ERROR") as captured,
        ):
            await maintenance.refresh_memory_state(uuid4(), uuid4(), uuid4(), uuid4())

        rendered = "\n".join(captured.output)
        self.assertIn("failed", rendered)
        self.assertIn("error_type=RuntimeError", rendered)
        self.assertNotIn(secret, rendered)


if __name__ == "__main__":
    unittest.main()
