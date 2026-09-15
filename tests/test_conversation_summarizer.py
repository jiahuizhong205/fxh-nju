"""Exercise summary persistence with real SQL; adapt sync SQLite to async calls."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import MetaData, Uuid, create_engine
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.models import Conversation, ConversationSummary, Message
from services.memory.summarizer import (
    generate_conversation_summary,
    persist_summary_if_revision_matches,
    refresh_conversation_summary,
)
from tests.test_conversation_memory import make_numbered_turns, make_snapshots


class _AsyncSqliteSession:
    """No extra driver: statements, transactions and row counts remain real SQL."""

    def __init__(self, engine):
        self.session = Session(engine, expire_on_commit=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        self.session.close()

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()


class SummaryGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_summary_is_deterministic_and_bounded(self):
        messages = make_snapshots([
            ("user", "我计划大二开始新闻学辅修"),
            ("assistant", "可以先修传播学概论"),
        ])
        first = await generate_conversation_summary("", messages, mock=True)
        second = await generate_conversation_summary("", messages, mock=True)
        self.assertEqual(first, second)
        self.assertIn("大二", first)
        self.assertIn("传播学概论", first)
        self.assertLessEqual(len(first), settings.chat_summary_max_characters)

    async def test_full_previous_summary_leaves_space_for_new_information(self):
        with patch.object(settings, "chat_summary_max_characters", 80):
            result = await generate_conversation_summary(
                "已确认新闻辅修。" * 100,
                make_snapshots([("user", "新增约束：周末不能上课"), ("assistant", "待确认平日课程")]),
                mock=True,
            )
        self.assertLessEqual(len(result), 80)
        self.assertIn("新闻辅修", result)
        self.assertIn("周末不能上课", result)

    async def test_real_generation_normalizes_and_caps_response(self):
        class Model:
            async def ainvoke(self, messages):
                self.messages = messages
                return SimpleNamespace(content="  已确认\r\n\r\n " + "结论 " * 100)

        model = Model()
        with patch.object(settings, "chat_summary_max_characters", 60):
            result = await generate_conversation_summary(
                "先前的目标", make_snapshots([("user", "新约束")]), mock=False, model=model,
            )
        self.assertLessEqual(len(result), 60)
        self.assertTrue(result.startswith("已确认"))
        self.assertNotIn("\r", result)
        self.assertIn("先前的目标", model.messages[-1].content)
        self.assertIn("新约束", model.messages[-1].content)
        for category in ("目标", "约束", "已确认事实", "未解决问题", "结论"):
            self.assertIn(category, model.messages[0].content)

    async def test_many_short_messages_still_produce_useful_bounded_mock_summary(self):
        messages = make_snapshots([
            *[("user", "历史问题")] * 100,
            ("user", "最后确认新闻辅修"),
        ])
        with patch.object(settings, "chat_summary_max_characters", 80):
            result = await generate_conversation_summary("", messages, mock=True)
        self.assertLessEqual(len(result), 80)
        self.assertIn("新闻辅修", result)


class SummaryPersistenceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        # The rest of the application schema includes PostgreSQL vector types.
        sqlite_metadata = MetaData()
        Conversation.__table__.to_metadata(sqlite_metadata)
        for model in (Message, ConversationSummary):
            table = model.__table__.to_metadata(sqlite_metadata)
            for column in table.columns:
                if isinstance(column.type, Uuid):
                    # SQLite's UUID affinity coerces digit-only UUIDs into ints.
                    column.type = Uuid(native_uuid=False)
            table.create(self.engine)
        self.addCleanup(self.engine.dispose)
        self.conversation_id = UUID(int=100)
        self.other_id = UUID(int=200)
        for name, value in (
            ("chat_recent_turn_limit", 1),
            ("chat_context_character_budget", 12_000),
            ("chat_summary_trigger_character_count", 1),
            ("mock_llm", True),
        ):
            self.enterContext(patch.object(settings, name, value))
        self.sessions = []

        def session_factory():
            session = _AsyncSqliteSession(self.engine)
            self.sessions.append(session)
            return session

        self.enterContext(patch("services.memory.summarizer.async_session", session_factory))

    def seed_messages(self, snapshots, conversation_id=None):
        with Session(self.engine) as db:
            db.add_all([
                Message(id=item.id, conversation_id=conversation_id or self.conversation_id,
                        role=item.role, content=item.content, created_at=item.created_at)
                for item in snapshots
            ])
            db.commit()

    def seed_summary(self, revision=2, cursor=None, conversation_id=None, summary="既有目标"):
        with Session(self.engine) as db:
            db.add(ConversationSummary(
                conversation_id=conversation_id or self.conversation_id,
                summary=summary, revision=revision, summarized_through_message_id=cursor,
            ))
            db.commit()

    def stored_summary(self, conversation_id=None):
        with Session(self.engine) as db:
            return db.get(ConversationSummary, conversation_id or self.conversation_id)

    async def test_refresh_creates_summary_and_second_refresh_is_idempotent(self):
        self.seed_messages(make_numbered_turns(3))
        first = await refresh_conversation_summary(self.conversation_id)
        row = self.stored_summary()
        self.assertEqual((first.updated, first.revision, first.summarized_message_count), (True, 1, 4))
        self.assertEqual(row.summarized_through_message_id, UUID(int=4))
        self.assertIn("问题 1", row.summary)
        self.assertNotIn("问题 3", row.summary)
        second = await refresh_conversation_summary(self.conversation_id)
        self.assertEqual((second.updated, second.revision, second.summarized_message_count), (False, 1, 0))
        self.assertEqual(self.stored_summary().summary, row.summary)
        self.assertEqual(len(self.sessions), 2)
        self.assertIsNot(self.sessions[0], self.sessions[1])

    async def test_refresh_skips_below_trigger_without_creating_row(self):
        self.seed_messages(make_numbered_turns(3))
        with patch.object(settings, "chat_summary_trigger_character_count", 100):
            result = await refresh_conversation_summary(self.conversation_id)
        self.assertFalse(result.updated)
        self.assertIsNone(self.stored_summary())

    async def test_trigger_counts_only_unsummarized_candidates_and_fires_at_boundary(self):
        self.seed_messages(make_snapshots([
            ("user", "旧" * 100), ("assistant", "已归档"),
            ("user", "abcd"), ("assistant", "efgh"),
            ("user", "最新问题"), ("assistant", "最新回答"),
            ("user", "未完成" * 100),
        ]))
        self.seed_summary(cursor=UUID(int=2))
        with patch.object(settings, "chat_summary_trigger_character_count", 11):
            below = await refresh_conversation_summary(self.conversation_id)
        self.assertFalse(below.updated)
        with patch.object(settings, "chat_summary_trigger_character_count", 10):
            result = await refresh_conversation_summary(self.conversation_id)
        self.assertEqual((result.updated, result.summarized_message_count), (True, 2))
        self.assertEqual(self.stored_summary().summarized_through_message_id, UUID(int=4))
        self.assertNotIn("未完成", self.stored_summary().summary)
        self.assertNotIn("已归档", self.stored_summary().summary)

    async def test_refresh_processes_only_oldest_prefix_within_serialized_input_budget(self):
        first_user = "最早用户" + "甲" * 30
        first_assistant = "最早回答" + "乙" * 30
        self.seed_messages(make_snapshots([
            ("user", first_user), ("assistant", first_assistant),
            ("user", "第二用户" + "丙" * 30), ("assistant", "第二回答" + "丁" * 30),
            ("user", "第三用户" + "戊" * 30), ("assistant", "第三回答" + "己" * 30),
            ("user", "保留问题"), ("assistant", "保留回答"),
        ]))

        class Model:
            async def ainvoke(self, messages):
                self.messages = messages
                return SimpleNamespace(content="第一批摘要")

        model = Model()
        with (
            patch.object(settings, "chat_context_character_budget", 220),
            patch.object(settings, "mock_llm", False),
            patch("services.memory.summarizer.create_chat_model", return_value=model),
        ):
            result = await refresh_conversation_summary(self.conversation_id)

        serialized_input = model.messages[-1].content
        payload = json.loads(serialized_input)
        self.assertLessEqual(len(serialized_input), 220)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "user", "content": first_user},
                {"role": "assistant", "content": first_assistant},
            ],
        )
        self.assertEqual((result.updated, result.summarized_message_count), (True, 2))
        self.assertEqual(self.stored_summary().summarized_through_message_id, UUID(int=2))

    async def test_single_oversized_turn_is_marked_bounded_and_advances_cursor(self):
        oversized_user = "超长问题" + "甲" * 500
        oversized_assistant = "超长回答" + "乙" * 500
        self.seed_messages(make_snapshots([
            ("user", oversized_user), ("assistant", oversized_assistant),
            ("user", "保留问题"), ("assistant", "保留回答"),
        ]))

        class Model:
            async def ainvoke(self, messages):
                self.messages = messages
                return SimpleNamespace(content="超长轮次摘要")

        model = Model()
        with (
            patch.object(settings, "chat_context_character_budget", 180),
            patch.object(settings, "mock_llm", False),
            patch("services.memory.summarizer.create_chat_model", return_value=model),
        ):
            result = await refresh_conversation_summary(self.conversation_id)

        serialized_input = model.messages[-1].content
        self.assertLessEqual(len(serialized_input), 180)
        self.assertIn("摘要输入已截断", serialized_input)
        self.assertEqual((result.updated, result.summarized_message_count), (True, 2))
        self.assertEqual(self.stored_summary().summarized_through_message_id, UUID(int=2))
        with Session(self.engine) as db:
            self.assertEqual(db.get(Message, UUID(int=1)).content, oversized_user)
            self.assertEqual(db.get(Message, UUID(int=2)).content, oversized_assistant)

    async def test_valid_cursor_outside_candidates_does_not_rebuild_older_messages(self):
        self.seed_messages(make_numbered_turns(3))
        self.seed_summary(cursor=UUID(int=6))
        result = await refresh_conversation_summary(self.conversation_id)
        self.assertFalse(result.updated)
        self.assertEqual(self.stored_summary().summarized_through_message_id, UUID(int=6))

    async def test_deleted_cursor_rebuilds_from_stored_summary_and_available_complete_turns(self):
        self.seed_messages(make_numbered_turns(3))
        self.seed_summary(cursor=UUID(int=999))
        result = await refresh_conversation_summary(self.conversation_id)
        row = self.stored_summary()
        self.assertEqual((result.updated, result.revision, result.summarized_message_count), (True, 3, 4))
        self.assertIn("既有目标", row.summary)
        self.assertIn("问题 1", row.summary)
        self.assertEqual(row.summarized_through_message_id, UUID(int=4))

    async def test_set_null_deleted_cursor_recovers_even_when_context_omits_summary(self):
        self.seed_messages(make_numbered_turns(3))
        self.seed_summary(cursor=None, summary="既有目标" * 100)
        with patch.object(settings, "chat_context_character_budget", 180):
            result = await refresh_conversation_summary(self.conversation_id)
        self.assertTrue(result.updated)
        self.assertIn("既有目标", self.stored_summary().summary)

    async def test_stale_revision_does_not_overwrite_new_summary(self):
        self.seed_summary(revision=3)
        async with _AsyncSqliteSession(self.engine) as db:
            result = await persist_summary_if_revision_matches(
                db, self.conversation_id, expected_revision=2,
                summary="过期摘要", through_message_id=UUID(int=2),
            )
            await db.commit()
        self.assertFalse(result.updated)
        self.assertEqual(result.revision, 3)
        self.assertEqual(self.stored_summary().summary, "既有目标")

    async def test_matching_revision_updates_only_target_conversation_and_caps_storage(self):
        self.seed_summary(revision=2)
        self.seed_summary(revision=2, conversation_id=self.other_id)
        with patch.object(settings, "chat_summary_max_characters", 20):
            async with _AsyncSqliteSession(self.engine) as db:
                result = await persist_summary_if_revision_matches(
                    db, self.conversation_id, expected_revision=2,
                    summary="有效摘要" * 100, through_message_id=UUID(int=2),
                )
                await db.commit()
        self.assertTrue(result.updated)
        self.assertEqual(self.stored_summary().revision, 3)
        self.assertEqual(self.stored_summary().summarized_through_message_id, UUID(int=2))
        self.assertLessEqual(len(self.stored_summary().summary), 20)
        self.assertEqual(self.stored_summary(self.other_id).revision, 2)

    async def test_concurrent_initial_refresh_loser_does_not_overwrite_winner(self):
        self.seed_messages(make_numbered_turns(3))

        async def concurrent_generation(*_args):
            self.seed_summary(revision=1, cursor=UUID(int=4), summary="较新摘要")
            return "过期摘要"

        with patch("services.memory.summarizer.generate_conversation_summary", concurrent_generation):
            result = await refresh_conversation_summary(self.conversation_id)
        self.assertFalse(result.updated)
        self.assertEqual(result.summarized_message_count, 0)
        self.assertEqual(self.stored_summary().summary, "较新摘要")

    async def test_empty_generation_does_not_advance_cursor_or_erase_summary(self):
        self.seed_messages(make_numbered_turns(3))
        self.seed_summary(cursor=UUID(int=2))

        async def empty_generation(*_args):
            return "   "

        with patch("services.memory.summarizer.generate_conversation_summary", empty_generation):
            result = await refresh_conversation_summary(self.conversation_id)
        self.assertFalse(result.updated)
        self.assertEqual(self.stored_summary().revision, 2)
        self.assertEqual(self.stored_summary().summary, "既有目标")

    async def test_generation_failure_preserves_cursor_and_summary(self):
        self.seed_messages(make_numbered_turns(3))
        self.seed_summary(cursor=UUID(int=2))

        async def failed_generation(*_args):
            raise TimeoutError("provider timeout")

        with patch("services.memory.summarizer.generate_conversation_summary", failed_generation):
            with self.assertRaises(TimeoutError):
                await refresh_conversation_summary(self.conversation_id)
        self.assertEqual(self.stored_summary().revision, 2)
        self.assertEqual(self.stored_summary().summarized_through_message_id, UUID(int=2))


if __name__ == "__main__":
    unittest.main()
