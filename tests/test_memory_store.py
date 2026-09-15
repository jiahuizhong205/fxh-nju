import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.models import UserMemory
from services.memory.extraction import MemoryCandidate
from services.memory.store import (
    delete_user_memory,
    update_user_memory,
    upsert_memory_candidates,
)


def _candidate(*, key, content, category="study_constraint", explicitly_requested=False):
    return MemoryCandidate(
        category=category,
        content=content,
        canonical_key=key,
        importance=0.8,
        confidence=0.9,
        explicitly_requested=explicitly_requested,
        evidence=content,
    )


class _EmptyScalarResult:
    def scalars(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _PostgresContractSession:
    def __init__(self):
        self.calls = []
        self.commit_count = 0
        self.rollback_count = 0

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    async def execute(self, statement, parameters=None):
        self.calls.append((statement, parameters or {}))
        if getattr(statement, "is_select", False):
            return _EmptyScalarResult()
        return SimpleNamespace(rowcount=1)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class MemoryStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(UserMemory.__table__.create)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.user_id = uuid.uuid4()
        self.conversation_id = uuid.uuid4()
        self.message_id = uuid.uuid4()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def _rows(self):
        result = await self.db.execute(select(UserMemory).order_by(UserMemory.created_at))
        return list(result.scalars().all())

    async def _upsert(self, candidates):
        return await upsert_memory_candidates(
            self.db,
            self.user_id,
            candidates,
            self.conversation_id,
            self.message_id,
        )

    async def test_same_canonical_key_updates_one_row(self):
        with patch.object(settings, "mock_llm", True):
            await self._upsert([_candidate(
                key="study_constraint:campus", content="优先鼓楼校区",
            )])
            count = await self._upsert([_candidate(
                key="study_constraint:campus", content="优先仙林校区",
            )])

        rows = await self._rows()
        self.assertEqual(count, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, "优先仙林校区")
        self.assertIsNone(rows[0].embedding)
        self.assertEqual(rows[0].embedding_provider, "")

    async def test_same_normalized_mock_content_merges_different_key(self):
        with patch.object(settings, "mock_llm", True):
            await self._upsert([_candidate(
                key="study_constraint:afternoon", content="我长期偏好下午课程",
            )])
            await self._upsert([_candidate(
                key="study_constraint:schedule", content="我长期偏好下午课程  ",
            )])

        rows = await self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].canonical_key, "study_constraint:afternoon")

    async def test_canonical_keys_are_isolated_by_user(self):
        other_user_id = uuid.uuid4()
        candidate = _candidate(
            key="study_constraint:campus", content="优先仙林校区",
        )
        with patch.object(settings, "mock_llm", True):
            await self._upsert([candidate])
            await upsert_memory_candidates(
                self.db,
                other_user_id,
                [candidate],
                uuid.uuid4(),
                uuid.uuid4(),
            )

        rows = await self._rows()
        self.assertEqual({row.user_id for row in rows}, {self.user_id, other_user_id})

    async def test_real_write_embeds_off_event_loop_before_persistence(self):
        event_loop_thread = threading.get_ident()
        embedding_threads = []

        def fake_embed(_text):
            embedding_threads.append(threading.get_ident())
            return [0.25] * 1024

        with (
            patch.object(settings, "mock_llm", False),
            patch("services.memory.store.embed_text", side_effect=fake_embed),
            patch("services.memory.store.embedding_signature", return_value="provider:test"),
        ):
            count = await self._upsert([_candidate(
                key="study_constraint:campus", content="优先仙林校区",
            )])

        rows = await self._rows()
        self.assertEqual(count, 1)
        self.assertEqual(rows[0].embedding_provider, "provider:test")
        self.assertEqual(len(rows[0].embedding), 1024)
        self.assertNotEqual(embedding_threads, [event_loop_thread])

    async def test_embedding_failure_happens_before_database_write(self):
        with (
            patch.object(settings, "mock_llm", False),
            patch("services.memory.store.embed_text", side_effect=RuntimeError("offline")),
        ):
            with self.assertRaisesRegex(RuntimeError, "offline"):
                await self._upsert([_candidate(
                    key="study_constraint:campus", content="优先仙林校区",
                )])

        self.assertEqual(await self._rows(), [])

    async def test_real_semantic_duplicate_merges_same_category_row(self):
        vectors = iter((
            [1.0] + [0.0] * 1023,
            [0.999] + [0.001] + [0.0] * 1022,
        ))
        with (
            patch.object(settings, "mock_llm", False),
            patch("services.memory.store.embed_text", side_effect=lambda _text: next(vectors)),
            patch("services.memory.store.embedding_signature", return_value="provider:test"),
        ):
            await self._upsert([_candidate(
                key="study_constraint:campus", content="我优先选择仙林校区",
            )])
            original_id = (await self._rows())[0].id
            await self._upsert([_candidate(
                key="study_constraint:location", content="我上课首选仙林校区",
            )])

        rows = await self._rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, original_id)
        self.assertEqual(rows[0].content, "我上课首选仙林校区")

    async def test_store_rechecks_credentials_and_fails_closed(self):
        with patch.object(settings, "mock_llm", True):
            count = await self._upsert([_candidate(
                key="confirmed_plan:secret",
                content="请记住 access_token=sk-secret-value",
                category="confirmed_plan",
                explicitly_requested=True,
            )])

        self.assertEqual(count, 0)
        self.assertEqual(await self._rows(), [])

    async def test_update_and_delete_are_user_scoped_hard_mutations(self):
        with patch.object(settings, "mock_llm", True):
            await self._upsert([_candidate(
                key="study_constraint:campus", content="优先鼓楼校区",
            )])
            memory = (await self._rows())[0]
            denied = await update_user_memory(
                self.db,
                uuid.uuid4(),
                memory.id,
                content="越权修改",
            )
            updated = await update_user_memory(
                self.db,
                self.user_id,
                memory.id,
                content="优先仙林校区",
                importance=0.95,
            )
            denied_delete = await delete_user_memory(
                self.db, uuid.uuid4(), memory.id,
            )

        self.assertIsNone(denied)
        self.assertIsNotNone(updated)
        self.assertEqual(updated.content, "优先仙林校区")
        self.assertEqual(updated.importance, 0.95)
        self.assertFalse(denied_delete)
        self.assertEqual(len(await self._rows()), 1)

        self.assertTrue(await delete_user_memory(self.db, self.user_id, memory.id))
        self.assertEqual(await self._rows(), [])

    async def test_update_rejects_credentials_without_touching_existing_row(self):
        with patch.object(settings, "mock_llm", True):
            await self._upsert([_candidate(
                key="study_constraint:campus", content="优先鼓楼校区",
            )])
            memory = (await self._rows())[0]
            with self.assertRaises(ValueError):
                await update_user_memory(
                    self.db,
                    self.user_id,
                    memory.id,
                    content="password is hunter2",
                    explicitly_requested=True,
                )

        rows = await self._rows()
        self.assertEqual(rows[0].content, "优先鼓楼校区")

    async def test_failed_commit_rolls_back_whole_upsert(self):
        with (
            patch.object(settings, "mock_llm", True),
            patch.object(self.db, "commit", side_effect=RuntimeError("commit failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "commit failed"):
                await self._upsert([
                    _candidate(
                        key="study_constraint:campus", content="优先仙林校区",
                    ),
                    _candidate(
                        key="study_constraint:schedule", content="我偏好下午课程",
                    ),
                ])

        self.assertFalse(self.db.in_transaction())
        self.assertEqual(await self._rows(), [])

    async def test_postgres_first_insert_locks_empty_category_and_uses_atomic_upsert(self):
        db = _PostgresContractSession()
        user_id = uuid.uuid4()
        with patch.object(settings, "mock_llm", True):
            count = await upsert_memory_candidates(
                db,
                user_id,
                [_candidate(
                    key="study_constraint:campus", content="优先仙林校区",
                )],
                self.conversation_id,
                self.message_id,
            )

        compiled = [
            str(statement.compile(dialect=postgresql.dialect()))
            for statement, _parameters in db.calls
        ]
        lock_index = next(
            index for index, sql in enumerate(compiled)
            if "pg_advisory_xact_lock" in sql
        )
        first_memory_select = next(
            index for index, sql in enumerate(compiled)
            if "FROM user_memories" in sql and sql.lstrip().startswith("SELECT")
        )
        upsert_sql = next(sql for sql in compiled if "ON CONFLICT" in sql)
        lock_parameters = db.calls[lock_index][1]

        self.assertEqual(count, 1)
        self.assertLess(lock_index, first_memory_select)
        self.assertEqual(
            lock_parameters["lock_key"],
            f"user-memory:{user_id}:study_constraint",
        )
        self.assertIn(
            "ON CONFLICT (user_id, canonical_key) DO UPDATE",
            upsert_sql,
        )
        self.assertIn("user_id", upsert_sql)
        self.assertEqual(db.commit_count, 1)
        self.assertEqual(db.rollback_count, 0)


if __name__ == "__main__":
    unittest.main()
