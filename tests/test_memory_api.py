import asyncio
import base64
import json
import threading
import unittest
import uuid
from types import SimpleNamespace
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import settings
from apps.api.database import engine
from apps.api.main import app
from apps.api.models import User, UserMemory
from apps.api.routes.memories import (
    MemoryCreate,
    MemoryUpdate,
    create_memory,
    delete_memory,
    get_memory,
    list_memories,
    update_memory,
)
from apps.api.routes.preferences import (
    MemoryPreferences,
    get_memory_preferences,
    save_memory_preferences,
)
from tests.memory_query_cases import REJECTED_QUERY_URLS, SAFE_QUERY_URLS
from services.memory.extraction import extract_memory_candidates
from services.memory.store import upsert_memory_candidates


def _row(user_id, *, updated_at, category="study_constraint", content="偏好下午课程"):
    memory_id = uuid.uuid4()
    return UserMemory(
        id=memory_id,
        user_id=user_id,
        canonical_key=f"{category}:manual-{memory_id.hex}",
        category=category,
        content=content,
        importance=0.5,
        confidence=1.0,
        embedding=None,
        embedding_provider="",
        created_at=updated_at,
        updated_at=updated_at,
    )


class _PreferenceDb:
    def __init__(self, error=None):
        self.commit_count = 0
        self.rollback_count = 0
        self.error = error

    async def commit(self):
        self.commit_count += 1
        if self.error is not None:
            raise self.error

    async def rollback(self):
        self.rollback_count += 1


class MemoryApiSchemaTests(unittest.TestCase):
    def test_application_engine_hides_sql_parameters(self):
        self.assertTrue(engine.sync_engine.hide_parameters)

    def test_memory_routes_are_registered_and_authenticated(self):
        expected = {
            ("/api/v1/memories", "GET"),
            ("/api/v1/memories", "POST"),
            ("/api/v1/memories/{memory_id}", "GET"),
            ("/api/v1/memories/{memory_id}", "PATCH"),
            ("/api/v1/memories/{memory_id}", "DELETE"),
            ("/api/v1/preferences/memory", "GET"),
            ("/api/v1/preferences/memory", "PUT"),
        }
        paths = app.openapi()["paths"]
        registered = {
            (path, method.upper())
            for path, operations in paths.items()
            for method in operations
        }
        self.assertTrue(expected.issubset(registered))

        for path, method in expected:
            parameters = paths[path][method.lower()].get("parameters", [])
            self.assertTrue(any(
                parameter["in"] == "header"
                and parameter["name"] == "authorization"
                for parameter in parameters
            ))

    def test_create_and_update_schemas_enforce_memory_contract(self):
        payload = MemoryCreate(category="career_goal", content="寻找内容运营实习")
        self.assertEqual(payload.importance, 0.5)
        with self.assertRaises(ValidationError):
            MemoryCreate(category="unknown", content="内容")
        with self.assertRaises(ValidationError):
            MemoryCreate(category="career_goal", content="x" * 501)
        with self.assertRaises(ValidationError):
            MemoryCreate(category="career_goal", content="内容", importance=1.01)
        with self.assertRaises(ValidationError):
            MemoryUpdate(content="")
        with self.assertRaises(ValidationError):
            MemoryUpdate(category="career_goal", unknown=True)

    def test_update_requires_at_least_one_non_null_field(self):
        for payload in (
            {},
            {"category": None},
            {"content": None},
            {"importance": None},
            {"category": None, "content": None, "importance": None},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                MemoryUpdate.model_validate(payload)

    def test_memory_preference_endpoints_publish_typed_responses(self):
        paths = app.openapi()["paths"]["/api/v1/preferences/memory"]
        for method in ("get", "put"):
            schema = paths[method]["responses"]["200"]["content"]["application/json"]["schema"]
            self.assertEqual(
                schema["$ref"],
                "#/components/schemas/MemoryPreferencesResponse",
            )


class MemoryApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(UserMemory.__table__.create)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.user = User(id=uuid.uuid4(), username="memory-owner")
        self.other_user = User(id=uuid.uuid4(), username="other-owner")

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def _all_rows(self):
        result = await self.db.execute(select(UserMemory))
        return list(result.scalars().all())

    async def test_mock_create_sanitizes_content_and_stores_no_vector(self):
        with patch.object(settings, "mock_llm", True):
            response = await create_memory(
                MemoryCreate(
                    category="study_constraint",
                    content="  我偏好   下午课程  ",
                    importance=0.8,
                ),
                self.user,
                self.db,
            )

        rows = await self._all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(response.id, rows[0].id)
        self.assertEqual(rows[0].content, "我偏好 下午课程")
        self.assertTrue(rows[0].canonical_key.startswith("study_constraint:"))
        self.assertIsNone(rows[0].embedding)
        self.assertEqual(rows[0].embedding_provider, "")

    async def test_real_create_embeds_off_event_loop_and_records_signature(self):
        event_loop_thread = threading.get_ident()
        embedding_threads = []

        def fake_embed(_content):
            embedding_threads.append(threading.get_ident())
            return [0.25] * 1024

        with (
            patch.object(settings, "mock_llm", False),
            patch("apps.api.routes.memories.embed_text", side_effect=fake_embed),
            patch("apps.api.routes.memories.embedding_signature", return_value="provider:test"),
        ):
            await create_memory(
                MemoryCreate(category="learning_goal", content="我想掌握数据分析"),
                self.user,
                self.db,
            )

        row = (await self._all_rows())[0]
        self.assertEqual(row.embedding_provider, "provider:test")
        self.assertEqual(len(row.embedding), 1024)
        self.assertNotEqual(embedding_threads, [event_loop_thread])

    async def test_manual_credentials_are_always_rejected_without_persistence(self):
        for secret in ("token=sk-secret-value", "验证码是 123456", "password=hunter2"):
            with self.subTest(secret=secret), patch.object(settings, "mock_llm", True):
                with self.assertRaises(HTTPException) as raised:
                    await create_memory(
                        MemoryCreate(category="confirmed_plan", content=secret),
                        self.user,
                        self.db,
                    )
                self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(await self._all_rows(), [])

    async def test_url_credentials_are_rejected_by_post_before_provider_or_persistence(self):
        rejected = (
            "https://alice:hunter2@example.com/course",
            "https://alice:x@example.com/course",
            "https://alice:hunter2＠example.com/path",
            *REJECTED_QUERY_URLS,
        )
        with (
            patch.object(settings, "mock_llm", False),
            patch("apps.api.routes.memories.embed_text", return_value=[0.25] * 1024) as embed,
            patch("apps.api.routes.memories.embedding_signature", return_value="provider:test") as signature,
        ):
            for content in rejected:
                with self.subTest(content=content):
                    with self.assertRaises(HTTPException) as raised:
                        await create_memory(
                            MemoryCreate(category="confirmed_plan", content=content),
                            self.user,
                            self.db,
                        )
                    self.assertEqual(raised.exception.status_code, 422)
                    self.assertEqual(raised.exception.detail, "该内容包含不能保存的认证秘密")

        self.assertEqual(embed.call_count, 0)
        self.assertEqual(signature.call_count, 0)
        self.assertEqual(await self._all_rows(), [])

    async def test_url_credentials_are_rejected_by_patch_before_provider_or_persistence(self):
        original = "我计划完成新闻学辅修"
        with patch.object(settings, "mock_llm", True):
            existing = await create_memory(
                MemoryCreate(category="confirmed_plan", content=original),
                self.user,
                self.db,
            )

        rejected = (
            "https://alice:hunter2@example.com/course",
            "https://alice:x@example.com/course",
            "https://alice:hunter2＠example.com/path",
            *REJECTED_QUERY_URLS,
        )
        with (
            patch.object(settings, "mock_llm", False),
            patch("services.memory.store.embed_text", return_value=[0.25] * 1024) as embed,
            patch("services.memory.store.embedding_signature", return_value="provider:test") as signature,
        ):
            for content in rejected:
                with self.subTest(content=content):
                    with self.assertRaises(HTTPException) as raised:
                        await update_memory(
                            existing.id,
                            MemoryUpdate(content=content),
                            self.user,
                            self.db,
                        )
                    self.assertEqual(raised.exception.status_code, 422)
                    self.assertEqual(raised.exception.detail, "该内容包含不能保存的认证秘密")

        self.assertEqual(embed.call_count, 0)
        self.assertEqual(signature.call_count, 0)
        rows = await self._all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, original)

    async def test_encoded_query_extraction_never_reaches_provider_or_persistence(self):
        evidence = "我长期偏好下午课程。"
        with (
            patch.object(settings, "mock_llm", False),
            patch("services.memory.store.embed_text", return_value=[0.25] * 1024) as embed,
            patch("services.memory.store.embedding_signature", return_value="provider:test") as signature,
        ):
            for url in REJECTED_QUERY_URLS:
                with self.subTest(url=url):
                    model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(
                        content=json.dumps({"memories": [{
                            "category": "study_constraint", "content": evidence,
                            "evidence": evidence, "canonical_key": "afternoon",
                            "importance": 0.8, "confidence": 0.9,
                        }]}, ensure_ascii=False),
                    )))
                    candidates = await extract_memory_candidates(
                        f"{evidence} 参考 {url}", mock=False, model=model,
                    )
                    stored = await upsert_memory_candidates(
                        self.db, self.user.id, candidates, uuid.uuid4(), uuid.uuid4(),
                    )
                    self.assertEqual(candidates, [])
                    self.assertEqual(stored, 0)
                    self.assertEqual(model.ainvoke.await_count, 0)
        self.assertEqual(embed.call_count, 0)
        self.assertEqual(signature.call_count, 0)
        self.assertEqual(await self._all_rows(), [])

    async def test_token_families_and_high_entropy_secrets_never_reach_providers(self):
        secrets = (
            "xox" + "b-111111111111-222222222222-AbCdEfGhIjKlMnOp",
            "github_pat_11AAAAAA0abcdefghijklmnopqrstuvwxyz",
            "glpat-AbCdEfGhIjKlMnOpQrSt",
            "npm_AbCdEfGhIjKlMnOpQrStUvWxYz012345",
            "Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "4a7d1ed414474e4033ac29ccb8653d9b7e0c1a59f2d4b6c8e0a1c3d5f7b9e2a4",
            "https://example.com/reset/Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "https://example.com/reset/4a7d1ed414474e4033ac29ccb8653d9b7e0c1a59f2d4b6c8e0a1c3d5f7b9e2a4",
            "https://example.com/reset?token=Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "https://example.com/reset?value=Q7vN4%5FcM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "https://example.com/reset#Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "aB3dE5fG7hI9jK1lM2nO4pQ6rS8tU0vW3xY5zA7bC9dE",
            "A8fK2mP7qR4sT9vW3xY6zB1cD5eF8gH2jL4nO7pQ9rS6tUV2",
        )
        with (
            patch.object(settings, "mock_llm", False),
            patch("apps.api.routes.memories.embed_text") as create_embed,
            patch("apps.api.routes.memories.embedding_signature") as create_signature,
            patch("services.memory.store.embed_text") as update_embed,
            patch("services.memory.store.embedding_signature") as update_signature,
        ):
            for secret in secrets:
                with self.subTest(operation="create", secret=secret):
                    with self.assertRaises(HTTPException) as raised:
                        await create_memory(
                            MemoryCreate(
                                category="confirmed_plan",
                                content=f"请记住这个值 {secret}",
                            ),
                            self.user,
                            self.db,
                        )
                    self.assertEqual(raised.exception.status_code, 422)

            with patch.object(settings, "mock_llm", True):
                existing = await create_memory(
                    MemoryCreate(
                        category="confirmed_plan",
                        content="我计划完成新闻学辅修",
                    ),
                    self.user,
                    self.db,
                )

            for secret in secrets:
                with self.subTest(operation="update", secret=secret):
                    with self.assertRaises(HTTPException) as raised:
                        await update_memory(
                            existing.id,
                            MemoryUpdate(content=f"请记住这个值 {secret}"),
                            self.user,
                            self.db,
                        )
                    self.assertEqual(raised.exception.status_code, 422)

        self.assertEqual(create_embed.call_count, 0)
        self.assertEqual(create_signature.call_count, 0)
        self.assertEqual(update_embed.call_count, 0)
        self.assertEqual(update_signature.call_count, 0)
        rows = await self._all_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, "我计划完成新闻学辅修")

    async def test_urls_and_course_slugs_are_not_rejected_as_high_entropy_secrets(self):
        safe_values = (
            "课程资料在 https://github.com/openai/openai-python/issues/1234",
            "课程资料在 https://token.example.com/course",
            "课程资料在 https://example.com/token-economics/",
            "I prefer the CS2026-Interdisciplinary-Course-Planning track",
            *SAFE_QUERY_URLS,
        )
        created_ids = []
        with patch.object(settings, "mock_llm", True):
            for content in safe_values:
                with self.subTest(content=content):
                    response = await create_memory(
                        MemoryCreate(category="confirmed_plan", content=content),
                        self.user,
                        self.db,
                    )
                    self.assertEqual(response.content, content)
                    created_ids.append(response.id)

            first_id = created_ids[0]
            for content in safe_values:
                with self.subTest(operation="patch", content=content):
                    response = await update_memory(
                        first_id,
                        MemoryUpdate(content=content),
                        self.user,
                        self.db,
                    )
                    self.assertEqual(response.content, content)

        rows = await self._all_rows()
        contents_by_id = {row.id: row.content for row in rows}
        self.assertEqual(contents_by_id[first_id], safe_values[-1])
        for memory_id, content in zip(created_ids[1:], safe_values[1:]):
            self.assertEqual(contents_by_id[memory_id], content)

    async def test_manual_sensitive_information_uses_explicit_endpoint_intent(self):
        with patch.object(settings, "mock_llm", True):
            response = await create_memory(
                MemoryCreate(
                    category="confirmed_plan",
                    content="我的联系电话是 13800138000",
                ),
                self.user,
                self.db,
            )
        self.assertEqual(response.content, "我的联系电话是 13800138000")

    async def test_whitespace_only_content_is_rejected_after_sanitization(self):
        with patch.object(settings, "mock_llm", True):
            with self.assertRaises(HTTPException) as raised:
                await create_memory(
                    MemoryCreate(category="learning_goal", content="   "),
                    self.user,
                    self.db,
                )
        self.assertEqual(raised.exception.status_code, 422)

    async def test_list_uses_stable_descending_cursor_without_gaps_or_duplicates(self):
        anchor = datetime(2026, 9, 14, 12, 0, 0)
        rows = [
            _row(self.user.id, updated_at=anchor - timedelta(minutes=index // 2), content=str(index))
            for index in range(7)
        ]
        other = _row(self.other_user.id, updated_at=anchor + timedelta(days=1), content="other")
        self.db.add_all([*rows, other])
        await self.db.commit()
        expected_ids = [
            item.id
            for item in sorted(rows, key=lambda item: (item.updated_at, item.id), reverse=True)
        ]

        seen = []
        cursor = None
        while True:
            page = await list_memories(
                self.user,
                self.db,
                category=None,
                cursor=cursor,
                limit=2,
            )
            seen.extend(item.id for item in page.items)
            cursor = page.next_cursor
            if cursor is None:
                break

        self.assertEqual(seen, expected_ids)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertNotIn(other.id, seen)

    async def test_cursor_is_url_safe_and_rejects_malformed_or_tampered_structure(self):
        now = datetime(2026, 9, 14, 12, 0, 0)
        self.db.add_all([
            _row(self.user.id, updated_at=now),
            _row(self.user.id, updated_at=now - timedelta(minutes=1)),
        ])
        await self.db.commit()
        page = await list_memories(
            self.user, self.db, category=None, cursor=None, limit=1,
        )
        self.assertIsNotNone(page.next_cursor)
        self.assertNotRegex(page.next_cursor, r"[+/]")

        tampered = base64.urlsafe_b64encode(json.dumps({
            "updated_at": now.isoformat(),
            "memory_id": str(uuid.uuid4()),
        }).encode()).decode().rstrip("=")
        for cursor in ("not!*base64", tampered):
            with self.subTest(cursor=cursor):
                with self.assertRaises(HTTPException) as raised:
                    await list_memories(
                        self.user,
                        self.db,
                        category=None,
                        cursor=cursor,
                        limit=20,
                    )
                self.assertEqual(raised.exception.status_code, 422)

    async def test_cursor_rejects_utc_normalization_overflow_as_422(self):
        cursor = base64.urlsafe_b64encode(json.dumps({
            "updated_at": "0001-01-01T00:00:00+23:59",
            "id": str(uuid.uuid4()),
        }).encode()).decode().rstrip("=")

        with self.assertRaises(HTTPException) as raised:
            await list_memories(
                self.user,
                self.db,
                category=None,
                cursor=cursor,
                limit=20,
            )

        self.assertEqual(raised.exception.status_code, 422)

    async def test_get_update_and_delete_hide_other_users_resource(self):
        memory = _row(
            self.other_user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
        )
        self.db.add(memory)
        await self.db.commit()

        for operation in (
            lambda: get_memory(memory.id, self.user, self.db),
            lambda: update_memory(
                memory.id,
                MemoryUpdate(content="越权修改"),
                self.user,
                self.db,
            ),
            lambda: delete_memory(memory.id, self.user, self.db),
        ):
            with self.assertRaises(HTTPException) as raised:
                await operation()
            self.assertEqual(raised.exception.status_code, 404)

        rows = await self._all_rows()
        self.assertEqual(rows[0].content, "偏好下午课程")

    async def test_update_keeps_category_key_and_embedding_derivatives_consistent(self):
        with patch.object(settings, "mock_llm", True):
            created = await create_memory(
                MemoryCreate(category="study_constraint", content="我偏好下午课程"),
                self.user,
                self.db,
            )
            updated = await update_memory(
                created.id,
                MemoryUpdate(
                    category="career_goal",
                    content="我希望从事内容运营",
                    importance=0.9,
                ),
                self.user,
                self.db,
            )

        row = (await self._all_rows())[0]
        self.assertEqual(updated.id, created.id)
        self.assertEqual(row.category, "career_goal")
        self.assertTrue(row.canonical_key.startswith("career_goal:"))
        self.assertEqual(row.content, "我希望从事内容运营")
        self.assertEqual(row.importance, 0.9)
        self.assertIsNone(row.embedding)
        self.assertEqual(row.embedding_provider, "")

    async def test_content_edit_detaches_old_semantic_key_with_stable_manual_key(self):
        memory = _row(
            self.user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
        )
        memory.canonical_key = "study_constraint:campus"
        self.db.add(memory)
        await self.db.commit()

        with patch.object(settings, "mock_llm", True):
            await update_memory(
                memory.id,
                MemoryUpdate(content="我偏好鼓楼校区的晚上课程"),
                self.user,
                self.db,
            )

        row = (await self._all_rows())[0]
        self.assertEqual(
            row.canonical_key,
            f"study_constraint:manual-{memory.id.hex}",
        )

    async def test_category_edit_uses_memory_id_based_manual_key(self):
        memory = _row(
            self.user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
        )
        memory.canonical_key = "study_constraint:campus"
        self.db.add(memory)
        await self.db.commit()

        with patch.object(settings, "mock_llm", True):
            await update_memory(
                memory.id,
                MemoryUpdate(category="career_goal"),
                self.user,
                self.db,
            )

        row = (await self._all_rows())[0]
        self.assertEqual(row.category, "career_goal")
        self.assertEqual(
            row.canonical_key,
            f"career_goal:manual-{memory.id.hex}",
        )

    async def test_category_edit_cannot_collide_with_same_semantic_suffix(self):
        first = _row(
            self.user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
            category="study_constraint",
        )
        first.canonical_key = "study_constraint:campus"
        second = _row(
            self.user.id,
            updated_at=datetime(2026, 9, 14, 11, 0, 0),
            category="career_goal",
        )
        second.canonical_key = "career_goal:campus"
        self.db.add_all([first, second])
        await self.db.commit()

        with patch.object(settings, "mock_llm", True):
            updated = await update_memory(
                first.id,
                MemoryUpdate(category="career_goal"),
                self.user,
                self.db,
            )

        rows = await self._all_rows()
        self.assertEqual(updated.id, first.id)
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row.canonical_key for row in rows},
            {
                f"career_goal:manual-{first.id.hex}",
                "career_goal:campus",
            },
        )

    async def test_update_rejects_secret_without_changing_existing_memory(self):
        with patch.object(settings, "mock_llm", True):
            created = await create_memory(
                MemoryCreate(category="study_constraint", content="我偏好下午课程"),
                self.user,
                self.db,
            )
            with self.assertRaises(HTTPException) as raised:
                await update_memory(
                    created.id,
                    MemoryUpdate(content="access_token=sk-secret-value"),
                    self.user,
                    self.db,
                )
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual((await self._all_rows())[0].content, "我偏好下午课程")

    async def test_real_patch_checks_ownership_before_calling_embedding_provider(self):
        owner_memory = _row(
            self.user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
        )
        other_memory = _row(
            self.other_user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
        )
        self.db.add_all([owner_memory, other_memory])
        await self.db.commit()
        owner_memory_id = owner_memory.id
        other_memory_id = other_memory.id
        sentinel = "SENTINEL EMBEDDING PROVIDER FAILURE"

        with (
            patch.object(settings, "mock_llm", False),
            patch("services.memory.store.embed_text", side_effect=RuntimeError(sentinel)) as embed,
        ):
            for memory_id in (other_memory_id, uuid.uuid4()):
                with self.subTest(memory_id=memory_id):
                    with self.assertRaises(HTTPException) as raised:
                        await update_memory(
                            memory_id,
                            MemoryUpdate(content="我偏好下午课程"),
                            self.user,
                            self.db,
                        )
                    self.assertEqual(raised.exception.status_code, 404)
                    self.assertEqual(embed.call_count, 0)

            with self.assertLogs("fuxiaohe.memory.api", level="ERROR") as captured:
                with self.assertRaises(HTTPException) as raised:
                    await update_memory(
                        owner_memory_id,
                        MemoryUpdate(content="我偏好下午课程"),
                        self.user,
                        self.db,
                    )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(embed.call_count, 1)
        self.assertNotIn(sentinel, raised.exception.detail)
        self.assertNotIn(sentinel, "\n".join(captured.output))

    async def test_owner_delete_hard_deletes_memory(self):
        memory = _row(
            self.user.id,
            updated_at=datetime(2026, 9, 14, 12, 0, 0),
        )
        memory.embedding = [0.5] * 1024
        self.db.add(memory)
        await self.db.commit()

        response = await delete_memory(memory.id, self.user, self.db)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(await self._all_rows(), [])

    async def test_create_database_failure_is_rolled_back_and_safely_reported(self):
        sentinel = "SENTINEL PRIVATE MEMORY BODY"
        with (
            patch.object(settings, "mock_llm", True),
            patch.object(self.db, "commit", side_effect=RuntimeError(sentinel)),
            self.assertLogs("fuxiaohe.memory.api", level="ERROR") as captured,
        ):
            with self.assertRaises(HTTPException) as raised:
                await create_memory(
                    MemoryCreate(category="confirmed_plan", content=sentinel),
                    self.user,
                    self.db,
                )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn(sentinel, raised.exception.detail)
        self.assertNotIn(sentinel, "\n".join(captured.output))
        self.assertIn("error_type=RuntimeError", "\n".join(captured.output))
        self.assertFalse(self.db.in_transaction())
        self.assertEqual(await self._all_rows(), [])

    async def test_provider_failure_is_not_exposed_or_logged_with_content(self):
        sentinel = "SENTINEL PROVIDER FAILURE WITH MEMORY BODY"
        with (
            patch.object(settings, "mock_llm", False),
            patch("apps.api.routes.memories.embed_text", side_effect=RuntimeError(sentinel)),
            self.assertLogs("fuxiaohe.memory.api", level="ERROR") as captured,
        ):
            with self.assertRaises(HTTPException) as raised:
                await create_memory(
                    MemoryCreate(category="confirmed_plan", content="我计划完成新闻学辅修"),
                    self.user,
                    self.db,
                )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn(sentinel, raised.exception.detail)
        self.assertNotIn(sentinel, "\n".join(captured.output))

    async def test_update_and_delete_failures_use_safe_generic_responses(self):
        sentinel = "SENTINEL SQL PARAMETER MEMORY BODY"
        cases = (
            (
                "update",
                "apps.api.routes.memories.update_user_memory",
                lambda: update_memory(
                    uuid.uuid4(),
                    MemoryUpdate(content="我偏好下午课程"),
                    self.user,
                    self.db,
                ),
            ),
            (
                "delete",
                "apps.api.routes.memories.delete_user_memory",
                lambda: delete_memory(uuid.uuid4(), self.user, self.db),
            ),
        )
        for operation, target, invoke in cases:
            with (
                self.subTest(operation=operation),
                patch(target, side_effect=RuntimeError(sentinel)),
                self.assertLogs("fuxiaohe.memory.api", level="ERROR") as captured,
            ):
                with self.assertRaises(HTTPException) as raised:
                    await invoke()
            self.assertEqual(raised.exception.status_code, 500)
            self.assertNotIn(sentinel, raised.exception.detail)
            self.assertNotIn(sentinel, "\n".join(captured.output))
            self.assertIn(f"operation={operation}", "\n".join(captured.output))

    async def test_read_database_failures_are_rolled_back_and_safely_reported(self):
        """Query failures must not leak database text through the public API."""
        sentinel = "SENTINEL READ SQL PARAMETER MEMORY BODY"
        cases = (
            (
                "list",
                lambda: list_memories(
                    self.user, self.db, category=None, cursor=None, limit=20,
                ),
            ),
            (
                "get",
                lambda: get_memory(uuid.uuid4(), self.user, self.db),
            ),
        )
        for operation, invoke in cases:
            with (
                self.subTest(operation=operation),
                patch.object(self.db, "execute", side_effect=RuntimeError(sentinel)),
                self.assertLogs("fuxiaohe.memory.api", level="ERROR") as captured,
            ):
                with self.assertRaises(HTTPException) as raised:
                    await invoke()
            self.assertEqual(raised.exception.status_code, 500)
            self.assertNotIn(sentinel, raised.exception.detail)
            self.assertNotIn(sentinel, "\n".join(captured.output))
            self.assertIn(f"operation={operation}", "\n".join(captured.output))
            self.assertFalse(self.db.in_transaction())


class MemoryPreferenceApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_and_put_memory_preferences_preserve_other_sections(self):
        user = User(
            id=uuid.uuid4(),
            preferences={
                "version": 1,
                "notifications": {"学习浇水提醒": True},
                "visibility": {"scope": "仅好友"},
                "memory": {"auto_capture_enabled": True},
            },
        )
        db = _PreferenceDb()

        before = await get_memory_preferences(user)
        saved = await save_memory_preferences(
            MemoryPreferences(auto_capture_enabled=False), user, db,
        )

        self.assertEqual(before, {"preferences": {"auto_capture_enabled": True}})
        self.assertEqual(saved, {"preferences": {"auto_capture_enabled": False}})
        self.assertFalse(user.preferences["memory"]["auto_capture_enabled"])
        self.assertEqual(user.preferences["notifications"], {"学习浇水提醒": True})
        self.assertEqual(user.preferences["visibility"]["scope"], "仅好友")
        self.assertEqual(db.commit_count, 1)

    async def test_memory_preferences_ignore_and_preserve_legacy_root_keys(self):
        original = {
            "version": 1,
            "memory": {"auto_capture_enabled": True},
            "knowledge_pathway_mode": "graph",
            "legacy_extension": {"enabled": True, "revision": 7},
        }
        user = User(id=uuid.uuid4(), preferences=original.copy())
        db = _PreferenceDb()

        before = await get_memory_preferences(user)
        saved = await save_memory_preferences(
            MemoryPreferences(auto_capture_enabled=False), user, db,
        )

        self.assertEqual(before, {"preferences": {"auto_capture_enabled": True}})
        self.assertEqual(saved, {"preferences": {"auto_capture_enabled": False}})
        self.assertEqual(user.preferences["knowledge_pathway_mode"], "graph")
        self.assertEqual(
            user.preferences["legacy_extension"],
            {"enabled": True, "revision": 7},
        )
        self.assertEqual(user.preferences["version"], 1)

    async def test_memory_preference_database_failure_is_safe_and_rolls_back(self):
        sentinel = "SENTINEL MEMORY PREFERENCE SQL PARAMETER"
        original = {
            "memory": {"auto_capture_enabled": True},
            "knowledge_pathway_mode": "graph",
        }
        user = User(id=uuid.uuid4(), preferences=original.copy())
        db = _PreferenceDb(error=RuntimeError(sentinel))

        with self.assertLogs("fuxiaohe.memory.preferences", level="ERROR") as captured:
            with self.assertRaises(HTTPException) as raised:
                await save_memory_preferences(
                    MemoryPreferences(auto_capture_enabled=False), user, db,
                )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn(sentinel, raised.exception.detail)
        self.assertNotIn(sentinel, "\n".join(captured.output))
        self.assertEqual(db.rollback_count, 1)
        self.assertEqual(user.preferences, original)


if __name__ == "__main__":
    unittest.main()
