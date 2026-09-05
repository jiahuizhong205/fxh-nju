"""后端契约与回归测试。

这些测试不连接数据库、Redis 或大模型，适合在业务接口补齐前作为稳定基线。
需要外部服务的集成测试应单独放置，避免把本地 mock 开发流程变成强依赖。
"""

import asyncio
import unittest
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from apps.api import config
from apps.api.models import Job, JobApplication, JobFavorite, KnowledgeProgress, LearningPlan, LearningRecord, RecommendationReport, User, UserContact
from apps.api.routes import account
from apps.api.routes import auth
from apps.api.routes import knowledge
from apps.api.routes import planning
from apps.api.routes import preferences


class _CommitOnlyDb:
    """change_password 当前只需要验证提交动作的最小 fake session。"""

    def __init__(self):
        self.commit_count = 0

    async def commit(self):
        self.commit_count += 1


class _Result:
    def __init__(self, rows=None, one=None):
        self.rows = rows or []
        self.one = one

    def scalars(self):
        return self

    def all(self):
        return self.rows

    def scalar_one_or_none(self):
        return self.one


class _FavoriteDb:
    def __init__(self, job=None, favorite=None, favorites=None):
        self.job = job
        self.favorite = favorite
        self.favorites = favorites or []
        self.added = []
        self.deleted = []
        self.commit_count = 0

    async def get(self, model, identifier):
        if model is Job:
            return self.job if self.job and self.job.id == identifier else None
        return None

    async def execute(self, _query):
        return _Result(rows=self.favorites, one=self.favorite)

    def add(self, item):
        self.added.append(item)

    async def delete(self, item):
        self.deleted.append(item)

    async def commit(self):
        self.commit_count += 1


class BackendContractTests(unittest.TestCase):
    def test_mock_llm_is_safe_by_default(self):
        self.assertTrue(config.Settings(_env_file=None).mock_llm)

    def test_compose_explicitly_defaults_to_mock(self):
        compose = Path(__file__).parents[1] / "infra" / "compose" / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")
        self.assertIn("MOCK_LLM: ${MOCK_LLM:-true}", content)

    def test_cors_allows_methods_used_by_account_plan_updates(self):
        main = Path(__file__).parents[1] / "apps" / "api" / "main.py"
        content = main.read_text(encoding="utf-8")
        self.assertIn('allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"]', content)

    def test_runtime_init_migrates_recommendation_report_stale_flag(self):
        database = Path(__file__).parents[1] / "apps" / "api" / "database.py"
        content = database.read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE recommendation_reports ADD COLUMN IF NOT EXISTS", content)
        self.assertIn("is_stale BOOLEAN NOT NULL DEFAULT FALSE", content)

    def test_password_policy_accepts_eight_to_twenty_alphanumeric_password(self):
        for password in ("Abcdef12", "NJU2026ok", "A1" + "x" * 18):
            auth._validate_password(password)

    def test_password_policy_rejects_short_long_or_missing_character_class(self):
        invalid_passwords = (
            "Abc1234",       # 少于 8 位
            "A1" + "x" * 19, # 超过 20 位
            "abcdefgh",      # 缺数字
            "12345678",      # 缺字母
        )
        for password in invalid_passwords:
            with self.subTest(password=password), self.assertRaises(HTTPException) as ctx:
                auth._validate_password(password)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_password_hash_round_trip(self):
        salt, digest = auth._hash_password("Correct123")
        self.assertTrue(auth._verify_password("Correct123", salt, digest))
        self.assertFalse(auth._verify_password("Wrong123", salt, digest))

    def test_change_password_rotates_token_and_updates_hash(self):
        old_password = "Oldpass123"
        new_password = "Newpass456"
        salt, digest = auth._hash_password(old_password)
        user = auth.User(
            username="test-user",
            password_hash=digest,
            salt=salt,
            nickname="测试用户",
            token="old-token",
        )
        db = _CommitOnlyDb()

        result = asyncio.run(
            auth.change_password(
                auth._ChangePassword(old_password=old_password, new_password=new_password),
                user,
                db,
            )
        )

        self.assertEqual(result["status"], "ok")
        self.assertNotEqual(result["token"], "old-token")
        self.assertEqual(user.token, result["token"])
        self.assertEqual(db.commit_count, 1)
        self.assertTrue(auth._verify_password(new_password, user.salt, user.password_hash))
        self.assertFalse(auth._verify_password(old_password, user.salt, user.password_hash))

    def test_change_password_rejects_invalid_new_password_before_mutating(self):
        old_password = "Oldpass123"
        salt, digest = auth._hash_password(old_password)
        user = auth.User(
            username="test-user-2",
            password_hash=digest,
            salt=salt,
            nickname="测试用户",
            token="unchanged-token",
        )
        db = _CommitOnlyDb()

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                auth.change_password(
                    auth._ChangePassword(old_password=old_password, new_password="12345678"),
                    user,
                    db,
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(user.token, "unchanged-token")
        self.assertEqual(db.commit_count, 0)
        self.assertTrue(auth._verify_password(old_password, user.salt, user.password_hash))

    def test_preferences_schema_accepts_existing_notification_labels(self):
        payload = preferences.PreferencesUpdate(
            preferences={
                "notifications": {
                    "学习浇水提醒": True,
                    "推荐报告完成": False,
                }
            }
        )
        self.assertEqual(payload.preferences.notifications["学习浇水提醒"], True)

    def test_preferences_schema_rejects_unknown_sections_and_non_boolean_values(self):
        with self.assertRaises(ValidationError):
            preferences.PreferencesUpdate(preferences={"unknown": {"value": 1}})
        with self.assertRaises(ValidationError):
            preferences.PreferencesUpdate(
                preferences={"notifications": {"学习浇水提醒": "yes"}}
            )

    def test_preference_sections_have_safe_defaults_and_validate_weekdays(self):
        data = preferences.PreferencesData()
        self.assertEqual(data.version, 1)
        self.assertFalse(data.learning_reminder.enabled is False)
        self.assertEqual(data.learning_reminder.time, "09:00")
        with self.assertRaises(ValidationError):
            preferences.PreferencesData(
                learning_reminder={"week_days": [0, 7]}
            )
        with self.assertRaises(ValidationError):
            preferences.PreferencesData(
                job_push={"locations": ["南京"], "job_types": ["实习", 3]}
            )

    def test_onboarding_status_is_persisted_on_account(self):
        user = User(
            username="onboarding-user",
            password_hash="hash",
            salt="salt",
            nickname="新用户",
            onboarding_completed=False,
        )
        db = _CommitOnlyDb()

        result = asyncio.run(
            auth.update_onboarding(
                auth._OnboardingUpdate(completed=True),
                user,
                db,
            )
        )

        self.assertTrue(result["onboarding_completed"])
        self.assertTrue(user.onboarding_completed)
        self.assertEqual(db.commit_count, 1)

    def test_job_favorite_can_be_added_idempotently(self):
        user = User(username="favorite-user", password_hash="hash", salt="salt")
        job = Job(id="job-test", employer="测试单位", title="测试岗位", location="南京", deadline="2026-12-31", source="test")
        db = _FavoriteDb(job=job)

        first = asyncio.run(planning.add_job_favorite("job-test", user, db))
        self.assertTrue(first["favorited"])
        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.commit_count, 1)
        self.assertIsInstance(db.added[0], JobFavorite)

        db.favorite = db.added[0]
        second = asyncio.run(planning.add_job_favorite("job-test", user, db))
        self.assertTrue(second["favorited"])
        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.commit_count, 1)

    def test_job_favorite_list_and_delete(self):
        user = User(username="favorite-user-2", password_hash="hash", salt="salt")
        first = JobFavorite(user_id=user.id, job_id="job-1")
        second = JobFavorite(user_id=user.id, job_id="job-2")
        db = _FavoriteDb(favorites=[first, second], favorite=first)

        result = asyncio.run(planning.list_job_favorites(user, db))
        self.assertEqual(result["job_ids"], ["job-1", "job-2"])

        deleted = asyncio.run(planning.remove_job_favorite("job-1", user, db))
        self.assertFalse(deleted["favorited"])
        self.assertEqual(db.deleted, [first])
        self.assertEqual(db.commit_count, 1)

    def test_job_favorite_rejects_missing_job(self):
        user = User(username="favorite-user-3", password_hash="hash", salt="salt")
        db = _FavoriteDb()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(planning.add_job_favorite("missing", user, db))
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(db.commit_count, 0)

    def test_contact_schema_normalizes_and_masks_supported_values(self):
        phone = account.ContactCreate(contact_type="phone", value="138 0013-8000")
        email = account.ContactCreate(contact_type="email", value="Student@nju.edu.cn")
        self.assertEqual(account._normalize_contact(phone.contact_type, phone.value), "13800138000")
        self.assertEqual(account._normalize_contact(email.contact_type, email.value), "student@nju.edu.cn")
        self.assertEqual(account._mask_contact("phone", "13800138000"), "138****8000")
        self.assertEqual(account._mask_contact("email", "student@nju.edu.cn"), "s*****@nju.edu.cn")

    def test_contact_schema_rejects_invalid_values(self):
        with self.assertRaises(ValidationError):
            account.ContactCreate(contact_type="phone", value="12345")
        with self.assertRaises(ValidationError):
            account.ContactCreate(contact_type="email", value="not-an-email")

    def test_learning_progress_summary_uses_only_completed_credits(self):
        records = [
            LearningRecord(course_name="新闻采访", term="2026春", credits=3, status="completed"),
            LearningRecord(course_name="新闻编辑", term="2026春", credits=2, status="in_progress"),
            LearningRecord(course_name="传播学", term="2026秋", credits=4, status="planned"),
        ]
        summary = account._summarize_learning_records(records)
        self.assertEqual(summary["completed_credits"], 3)
        self.assertEqual(summary["in_progress_credits"], 2)
        self.assertEqual(summary["planned_credits"], 4)
        self.assertEqual(summary["total_credits"], 9)

    def test_recommendation_report_keeps_profile_version_and_payload(self):
        report = RecommendationReport(
            user_id="00000000-0000-0000-0000-000000000001",
            profile_version=3,
            profile_snapshot={"major": "新闻学", "grade": "大二"},
            recommendations=[{"program": {"name": "新闻学"}, "total_score": 86}],
        )
        self.assertEqual(report.profile_version, 3)
        self.assertEqual(report.profile_snapshot["major"], "新闻学")
        self.assertEqual(report.recommendations[0]["total_score"], 86)
        self.assertFalse(report.is_stale)

    def test_learning_plan_keeps_snapshot_and_adoption_state(self):
        plan = LearningPlan(
            user_id="00000000-0000-0000-0000-000000000001",
            program_name="新闻学",
            profile_version=4,
            status="draft",
            items=[{"course": "新闻采访与写作", "semester": 3, "credits": 3}],
            alternatives=[],
            warnings=["需要跨校区通勤"],
        )
        self.assertEqual(plan.status, "draft")
        self.assertEqual(plan.items[0]["course"], "新闻采访与写作")
        self.assertEqual(plan.profile_version, 4)

    def test_job_application_keeps_account_status_and_tracking_fields(self):
        application = JobApplication(
            user_id="00000000-0000-0000-0000-000000000001",
            job_id="job-test",
            status="interview",
            channel="官网",
            note="已完成一面",
        )
        self.assertEqual(application.status, "interview")
        self.assertEqual(application.channel, "官网")
        self.assertEqual(application.note, "已完成一面")

    def test_knowledge_progress_keeps_node_status_and_completion(self):
        progress = KnowledgeProgress(
            user_id="00000000-0000-0000-0000-000000000001",
            node_id="k003",
            status="progress",
            progress_percent=60,
        )
        self.assertEqual(progress.node_id, "k003")
        self.assertEqual(progress.status, "progress")
        self.assertEqual(progress.progress_percent, 60)

    def test_knowledge_progress_schema_rejects_out_of_range_completion(self):
        payload = knowledge.KnowledgeProgressUpdate(status="done", progress_percent=100)
        self.assertEqual(payload.progress_percent, 100)
        with self.assertRaises(ValidationError):
            knowledge.KnowledgeProgressUpdate(status="done", progress_percent=101)


if __name__ == "__main__":
    unittest.main()
