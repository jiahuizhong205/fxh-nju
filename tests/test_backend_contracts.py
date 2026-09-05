"""后端契约与回归测试。

这些测试不连接数据库、Redis 或大模型，适合在业务接口补齐前作为稳定基线。
需要外部服务的集成测试应单独放置，避免把本地 mock 开发流程变成强依赖。
"""

import asyncio
import unittest
import uuid
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError

from apps.api import config
from apps.api.models import CacheInvalidation, Feedback, FeedbackAttachment, Job, JobApplication, JobFavorite, KnowledgeProgress, LearningActivity, LearningPlan, LearningRecord, Notification, PasswordHistory, ProgramEnrollment, RecommendationReport, SyncRecord, User, UserAccountLink, UserAvatar, UserContact, UserSession, VerificationChallenge, utcnow
from apps.api.routes import account
from apps.api.routes import auth
from apps.api.routes import knowledge
from apps.api.routes import planning
from apps.api.routes import preferences
from apps.api.routes import profile
from apps.api.routes import sync
from apps.api.routes import notifications
from apps.api.routes import cache
from apps.api.routes import meta
from apps.api.routes import feedback
from packages.contracts.schemas import ChatRequest
from services.planning.recommendation_engine import hard_filter, recommend
from services.planning.eligibility import evaluate_program_eligibility
from services.planning.schedule_conflicts import detect_schedule_conflicts
from services.planning.schedule_conflicts import build_schedule_options
from services.planning.career_engine import build_career_outcomes
from services.rag.knowledge_graph import get_learning_pathways, get_node_resources, get_skill_pathways


class _CommitOnlyDb:
    """change_password 当前只需要验证提交动作的最小 fake session。"""

    def __init__(self):
        self.commit_count = 0
        self.added = []

    async def execute(self, _query):
        return _Result(rows=self.added)

    def add(self, item):
        self.added.append(item)

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
        self.assertIn("ALTER TABLE courses ADD COLUMN IF NOT EXISTS schedule", content)

    def test_password_policy_accepts_eight_to_twenty_alphanumeric_password(self):
        for password in ("Abcdef12", "NJU2026ok", "A1" + "x" * 18):
            auth._validate_password(password)

    def test_mock_embedding_does_not_load_local_model(self):
        from services.rag import retrieval

        retrieval._embedding_model = None
        retrieval._use_api = False
        retrieval._placeholder_only = False
        retrieval._init_local_model()
        self.assertTrue(retrieval._placeholder_only)
        first = retrieval.embed_text("同一段文字")
        second = retrieval.embed_text("同一段文字")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 384)

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

    def test_change_password_rejects_recent_password_reuse(self):
        old_password = "Current123"
        previous_password = "Previous123"
        salt, digest = auth._hash_password(old_password)
        previous_salt, previous_digest = auth._hash_password(previous_password)
        user = auth.User(
            username="test-user-3",
            password_hash=digest,
            salt=salt,
            nickname="测试用户",
            token="unchanged-token",
        )
        db = _CommitOnlyDb()
        db.added.append(
            PasswordHistory(
                user_id=user.id,
                password_hash=previous_digest,
                salt=previous_salt,
            )
        )

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                auth.change_password(
                    auth._ChangePassword(old_password=old_password, new_password=previous_password),
                    user,
                    db,
                )
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(db.commit_count, 0)
        self.assertEqual(user.token, "unchanged-token")

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

    def test_preference_section_merge_does_not_drop_other_settings(self):
        merged = preferences._merge_preference_section(
            {"version": 1, "notifications": {"学习浇水提醒": True}},
            "job_push",
            {"enabled": False, "locations": ["南京"]},
        )
        self.assertFalse(merged["job_push"]["enabled"])
        self.assertEqual(merged["notifications"]["学习浇水提醒"], True)

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

    def test_job_detail_serializes_design_fields(self):
        job = Job(
            id="job-detail",
            employer="测试单位",
            title="内容实习生",
            location="南京",
            deadline="2026-12-31",
            source="test",
            remote_type="混合办公",
            job_type="实习",
            arrival_time="每周至少 3 天",
            internship_duration="3 个月",
            responsibilities=["内容整理", "数据分析"],
            application_email="hr@example.com",
            application_note="请附个人简历",
        )
        serialized = planning._job_dict(job)
        self.assertEqual(serialized["remote_type"], "混合办公")
        self.assertEqual(serialized["responsibilities"], ["内容整理", "数据分析"])
        self.assertEqual(serialized["application_email"], "hr@example.com")

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

    def test_verification_challenge_stores_only_digest_and_consumes_once(self):
        code, salt, digest = account._new_verification_code()
        challenge = VerificationChallenge(
            code_hash=digest,
            code_salt=salt,
            expires_at=utcnow() + timedelta(minutes=10),
            max_attempts=2,
        )
        self.assertNotEqual(code, challenge.code_hash)
        self.assertEqual(account._verify_challenge_code(challenge, code), (True, "ok"))
        self.assertEqual(account._verify_challenge_code(challenge, code), (False, "验证码已失效"))

    def test_verification_challenge_expires_and_limits_attempts(self):
        code, salt, digest = account._new_verification_code()
        challenge = VerificationChallenge(
            code_hash=digest,
            code_salt=salt,
            expires_at=utcnow() - timedelta(seconds=1),
            max_attempts=2,
        )
        self.assertEqual(account._verify_challenge_code(challenge, code)[1], "验证码已过期")
        self.assertTrue(challenge.consumed)

        code, salt, digest = account._new_verification_code()
        challenge = VerificationChallenge(
            code_hash=digest,
            code_salt=salt,
            expires_at=utcnow() + timedelta(minutes=10),
            max_attempts=2,
        )
        self.assertEqual(account._verify_challenge_code(challenge, "000000")[1], "验证码错误")
        self.assertEqual(account._verify_challenge_code(challenge, "000000")[1], "验证码错误")
        self.assertTrue(challenge.consumed)

    def test_visibility_policy_is_conservative_for_friend_scope(self):
        self.assertTrue(profile._can_view_profile("仅自己", is_self=True, same_major=False))
        self.assertTrue(profile._can_view_profile("全校公开", is_self=False, same_major=False))
        self.assertTrue(profile._can_view_profile("同专业同学", is_self=False, same_major=True))
        self.assertFalse(profile._can_view_profile("同专业同学", is_self=False, same_major=False))
        self.assertFalse(profile._can_view_profile("仅好友", is_self=False, same_major=True))

    def test_cache_clear_scopes_are_account_scoped_and_non_destructive(self):
        payload = cache.CacheClearRequest(scopes=["images", "recommendations"])
        self.assertEqual(payload.scopes, ["images", "recommendations"])
        record = CacheInvalidation(scope="images", generation=2)
        self.assertEqual(cache._serialize(record, "images")["generation"], 2)
        self.assertEqual(cache._serialize(None, "conversations")["generation"], 0)

    def test_product_metadata_is_centralized_for_about_page(self):
        self.assertEqual(meta.PRODUCT_METADATA["product_name"], "福小禾")
        self.assertEqual(meta.PRODUCT_METADATA["birth_year"], 2026)
        self.assertTrue(any(item["key"] == "planning" for item in meta.PRODUCT_METADATA["features"]))

    def test_account_link_requires_explicit_relation_for_switching(self):
        current_id = "00000000-0000-0000-0000-000000000001"
        target_id = "00000000-0000-0000-0000-000000000002"
        self.assertTrue(auth._can_switch_account(current_id, target_id, {target_id}))
        self.assertFalse(auth._can_switch_account(current_id, target_id, set()))
        self.assertFalse(auth._can_switch_account(current_id, current_id, {current_id}))
        link = UserAccountLink(owner_user_id=current_id, linked_user_id=target_id)
        self.assertEqual(str(link.linked_user_id), target_id)

    def test_avatar_upload_validates_type_and_size_before_storage(self):
        profile._validate_avatar("image/png", b"png-bytes")
        with self.assertRaises(ValueError):
            profile._validate_avatar("text/plain", b"not-image")
        with self.assertRaises(ValueError):
            profile._validate_avatar("image/png", b"")
        avatar = UserAvatar(content_type="image/png", data=b"png-bytes", size_bytes=9)
        self.assertEqual(avatar.size_bytes, 9)

    def test_feedback_attachment_validates_upload_and_keeps_digest(self):
        feedback._validate_attachment("image/png", b"png-bytes")
        with self.assertRaises(ValueError):
            feedback._validate_attachment("text/plain", b"not-image")
        attachment = FeedbackAttachment(
            filename="screen.png",
            content_type="image/png",
            data=b"png-bytes",
            size_bytes=9,
            sha256="a" * 64,
        )
        self.assertEqual(attachment.filename, "screen.png")
        self.assertEqual(len(attachment.sha256), 64)

    def test_unverified_contact_cannot_become_primary(self):
        contact = UserContact(contact_type="phone", value="13800138000", verified=False, is_primary=False)
        self.assertFalse(contact.is_primary)
        contact.verified = True
        contact.is_primary = True
        self.assertTrue(contact.verified and contact.is_primary)

    def test_password_reset_requires_verified_contact_and_uses_separate_purpose(self):
        request = account.PasswordResetRequest(username="student", contact_type="email")
        confirm = account.PasswordResetConfirm(
            username="student",
            contact_type="email",
            code="123456",
            new_password="Reset1234",
        )
        self.assertEqual(request.contact_type, "email")
        self.assertEqual(confirm.new_password, "Reset1234")
        challenge = VerificationChallenge(purpose="password_reset")
        self.assertEqual(challenge.purpose, "password_reset")
        self.assertEqual(
            account._challenge_purpose_clause("contact_verification").right.value,
            "contact_verification",
        )
        self.assertEqual(
            account._challenge_purpose_clause("password_reset").right.value,
            "password_reset",
        )

    def test_schedule_options_prioritize_user_campus_and_report_missing_courses(self):
        options = build_schedule_options(
            [{"course": "新闻采访与写作", "credits": 3}, {"course": "传播学概论", "credits": 3}],
            [
                {"course_name": "新闻采访与写作", "campus": "鼓楼校区", "teaching_class_id": "TC-2"},
                {"course_name": "新闻采访与写作", "campus": "仙林校区", "teaching_class_id": "TC-1"},
            ],
            user_campus="仙林校区",
        )
        self.assertEqual(options["courses"][0]["offerings"][0]["teaching_class_id"], "TC-1")
        self.assertEqual(options["missing_courses"], ["传播学概论"])
        self.assertFalse(options["all_available"])

    def test_schedule_options_put_full_classes_after_available_classes(self):
        options = build_schedule_options(
            [{"course": "传播学概论", "credits": 3}],
            [
                {"course_name": "传播学概论", "campus": "仙林校区", "teaching_class_id": "FULL", "is_full": True},
                {"course_name": "传播学概论", "campus": "仙林校区", "teaching_class_id": "OPEN", "is_full": False},
            ],
            user_campus="仙林校区",
        )
        self.assertEqual(options["courses"][0]["offerings"][0]["teaching_class_id"], "OPEN")

    def test_saved_plan_csv_export_keeps_traceable_plan_metadata(self):
        plan = LearningPlan(
            id="00000000-0000-0000-0000-000000000001",
            program_name="新闻学",
            profile_version=3,
            status="adopted",
            items=[{"term": "秋季", "year": 1, "course": "传播学概论", "credits": 3, "campus": "仙林校区"}],
        )
        exported = planning._plan_csv(plan)
        self.assertIn("计划ID,专业,画像版本,计划状态", exported)
        self.assertIn("新闻学", exported)
        self.assertIn("传播学概论", exported)

    def test_queued_in_app_notification_advances_to_sent_when_due(self):
        notification = Notification(
            channel="in_app",
            status="queued",
            scheduled_at=utcnow() - timedelta(seconds=1),
        )
        self.assertTrue(notifications._deliver_in_app(notification))
        self.assertEqual(notification.status, "sent")
        self.assertIsNotNone(notification.sent_at)

    def test_future_or_external_notification_is_not_marked_sent(self):
        notification = Notification(
            channel="email",
            status="queued",
            scheduled_at=utcnow() - timedelta(seconds=1),
        )
        self.assertFalse(notifications._deliver_in_app(notification))
        self.assertEqual(notification.status, "queued")

    def test_user_session_uses_digest_and_expiration_for_activity(self):
        token = "opaque-session-token"
        session = auth._new_session("00000000-0000-0000-0000-000000000001", token)
        self.assertEqual(session.token_hash, auth._hash_session_token(token))
        self.assertNotEqual(session.token_hash, token)
        self.assertTrue(auth._session_is_active(session))
        session.revoked_at = utcnow()
        self.assertFalse(auth._session_is_active(session))

    def test_user_session_serialization_exposes_metadata_not_token(self):
        session = UserSession(
            user_agent="browser",
            ip_address="127.0.0.1",
            token_hash="a" * 64,
            expires_at=utcnow() + timedelta(days=1),
        )
        serialized = auth._serialize_session(session)
        self.assertIn("user_agent", serialized)
        self.assertNotIn("token_hash", serialized)

    def test_logout_only_clears_current_legacy_token(self):
        user = User(token="current-token")

        auth._clear_legacy_token(user, "older-session-token")
        self.assertEqual(user.token, "current-token")

        auth._clear_legacy_token(user, "current-token")
        self.assertIsNone(user.token)

    def test_saved_plan_can_request_schedule_preview_for_selected_classes(self):
        payload = planning.ConflictCheckRequest(teaching_class_ids=["TC-001", "TC-002"])
        self.assertEqual(payload.teaching_class_ids, ["TC-001", "TC-002"])
        plan = LearningPlan(program_name="新闻学", schedule_analysis={"feasible": False})
        self.assertFalse(planning._saved_plan_dict(plan)["schedule_analysis"]["feasible"])

    def test_recalculate_saved_plan_refreshes_profile_and_clears_stale_analysis(self):
        plan = LearningPlan(
            program_name="新闻学",
            profile_version=2,
            items=[{"course": "旧课程", "credits": 3}],
            schedule_analysis={"feasible": False},
        )
        generated = SimpleNamespace(
            program_name="新闻学",
            items=[SimpleNamespace(semester=2, term="秋季", year=1, course="新课程", credits=3, campus="仙林校区")],
            alternatives=[],
            warnings=["请关注校区通勤"],
            infeasible=False,
        )

        planning._apply_generated_plan(plan, generated, profile_version=3)

        self.assertEqual(plan.profile_version, 3)
        self.assertEqual(plan.items[0]["course"], "新课程")
        self.assertEqual(plan.warnings, ["请关注校区通勤"])
        self.assertEqual(plan.schedule_analysis, {})

    def test_career_outcomes_are_explained_by_jobs_and_skill_paths(self):
        outcomes = build_career_outcomes(
            [{
                "skill_name": "新闻采写能力",
                "knowledge_points": ["新闻价值判断"],
                "careers": ["记者/编辑"],
            }],
            [{
                "title": "实习记者",
                "skills_required": ["新闻采写能力"],
                "skills_preferred": [],
            }],
        )
        self.assertEqual(outcomes[0]["career"], "记者/编辑")
        self.assertEqual(outcomes[0]["related_job_count"], 1)
        self.assertEqual(outcomes[0]["job_titles"], ["实习记者"])
        self.assertIn("岗位表", outcomes[0]["evidence"])

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

    def test_learning_completion_percentage_is_bounded_and_target_aware(self):
        self.assertEqual(account._calculate_completion_percent(28, 50), 56)
        self.assertEqual(account._calculate_completion_percent(80, 50), 100)
        self.assertEqual(account._calculate_completion_percent(1, 0), 0)

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

    def test_knowledge_pathways_use_knowledge_points_for_skill_mapping(self):
        pathways = get_skill_pathways("新闻学")
        self.assertTrue(pathways)
        self.assertTrue(any(pathway["careers"] for pathway in pathways))
        self.assertIn("记者/编辑", {career for pathway in pathways for career in pathway["careers"]})

    def test_knowledge_resources_and_pathway_modes_are_available(self):
        resources = get_node_resources("k003")
        self.assertTrue(resources)
        self.assertEqual(resources[0]["resource_type"], "knowledge_note")
        self.assertEqual(get_node_resources("missing"), [])
        pathways = get_learning_pathways("新闻学", "self_study")
        self.assertTrue(pathways)
        self.assertTrue(all(pathway["mode"] == "self_study" for pathway in pathways))

    def test_learning_growth_summary_uses_real_knowledge_activity_and_course_data(self):
        summary = knowledge._learning_growth_summary(
            [KnowledgeProgress(progress_percent=100), KnowledgeProgress(progress_percent=50)],
            [LearningActivity(activity_date=date(2026, 9, 5))],
            [LearningRecord(status="completed", credits=3)],
            target_credits=6,
        )
        self.assertEqual(summary["knowledge_percent"], 75)
        self.assertEqual(summary["completed_credits"], 3)
        self.assertEqual(summary["course_percent"], 50)
        self.assertEqual(summary["growth_percent"], 43)

    def test_profile_schedule_schema_accepts_supported_preferences_only(self):
        payload = profile.ProfileUpdate(
            major="新闻学",
            grade="大二",
            schedule_preferences={
                "energy_period": "黄金档",
                "time_slots": ["上午黄金档", "午后时光"],
                "concentration": "均匀分散",
                "nap": "需要午休",
                "prefer_late": False,
                "conflict_strategies": ["跨校区通勤", "优先选择线上/混合课程"],
            },
        )
        self.assertEqual(payload.schedule_preferences.concentration, "均匀分散")
        with self.assertRaises(ValidationError):
            profile.ProfileUpdate(
                major="新闻学",
                grade="大二",
                schedule_preferences={"concentration": "随便排"},
            )
        with self.assertRaises(ValidationError):
            profile.ProfileUpdate(
                major="新闻学",
                grade="大二",
                schedule_preferences={"unknown": True},
            )

    def test_profile_options_are_versioned_and_profile_values_are_whitelisted(self):
        options = profile.get_profile_options()
        self.assertEqual(options["version"], 1)
        self.assertIn("数据分析", options["interests"])
        self.assertIn("编程基础", options["strengths"])
        with self.assertRaises(ValidationError):
            profile.ProfileUpdate(
                major="新闻学",
                grade="大二",
                interests=["不存在的兴趣"],
            )

    def test_sync_record_keeps_scope_version_and_status(self):
        record = SyncRecord(
            user_id="00000000-0000-0000-0000-000000000001",
            scope="learning_records",
            version=3,
            status="synced",
        )
        self.assertEqual(record.scope, "learning_records")
        self.assertEqual(record.version, 3)
        self.assertEqual(record.status, "synced")

    def test_sync_request_rejects_unknown_scopes(self):
        payload = sync.SyncRequest(scopes=["profile", "learning_records"])
        self.assertEqual(payload.scopes, ["profile", "learning_records"])
        self.assertIsNotNone(payload.request_id)
        record = SyncRecord(
            scope="profile",
            last_request_id=str(payload.request_id),
            retry_count=1,
        )
        self.assertTrue(sync._is_duplicate_request(record, payload.request_id))
        self.assertFalse(sync._is_duplicate_request(record, uuid.uuid4()))
        with self.assertRaises(ValidationError):
            sync.SyncRequest(scopes=["unknown"])

    def test_notification_keeps_delivery_and_read_state(self):
        item = Notification(
            user_id="00000000-0000-0000-0000-000000000001",
            category="recommendation",
            title="推荐报告已生成",
            body="你的推荐报告已准备好",
            channel="in_app",
            status="queued",
        )
        self.assertEqual(item.category, "recommendation")
        self.assertEqual(item.status, "queued")
        self.assertIsNone(item.read_at)

    def test_notification_request_validates_supported_channels(self):
        payload = notifications.NotificationReadRequest(read=True)
        self.assertTrue(payload.read)

    def test_program_enrollment_keeps_account_and_program_relationship(self):
        enrollment = ProgramEnrollment(
            user_id="00000000-0000-0000-0000-000000000001",
            program_name="新闻学",
            status="active",
        )
        self.assertEqual(enrollment.program_name, "新闻学")
        self.assertEqual(enrollment.status, "active")

    def test_feedback_keeps_processing_status_and_update_time(self):
        feedback = Feedback(
            user_id="00000000-0000-0000-0000-000000000001",
            feedback_type="功能建议",
            content="希望增加课程提醒",
            status="in_progress",
        )
        self.assertEqual(feedback.status, "in_progress")

    def test_password_history_keeps_previous_credential_metadata(self):
        history = PasswordHistory(
            user_id="00000000-0000-0000-0000-000000000001",
            password_hash="old-hash",
            salt="old-salt",
        )
        self.assertEqual(history.password_hash, "old-hash")
        self.assertEqual(history.salt, "old-salt")

    def test_completed_math_course_satisfies_math_prerequisite_signal(self):
        result = hard_filter(
            {
                "name": "计算机科学与技术",
                "campus": "仙林校区",
                "required_math": True,
                "required_math_level": "高等数学（一）",
                "semesters_needed": 4,
                "total_credits": 45,
            },
            {
                "major": "新闻学",
                "grade": "大二",
                "campus": "仙林校区",
                "math_willingness": False,
                "certificate_goal": "degree",
                "completed_courses": ["高等数学（一）"],
            },
        )
        self.assertTrue(result.passed)
        self.assertNotIn("不接受修高数", " ".join(result.reasons))

    def test_program_eligibility_reports_missing_courses_and_manual_review(self):
        result = evaluate_program_eligibility(
            {
                "name": "新闻学",
                "total_credits": 6,
                "required_math": False,
            },
            [
                {"course": "新闻采访与写作", "credits": 3},
                {"course": "传播学概论", "credits": 3},
            ],
            [{"course_name": "新闻采访与写作", "credits": 3, "status": "completed"}],
        )
        self.assertFalse(result["estimated_eligible"])
        self.assertTrue(result["requires_manual_review"])
        self.assertEqual(result["missing_courses"], ["传播学概论"])
        self.assertEqual(result["completed_credits"], 3.0)
        self.assertTrue(any("尚缺" in reason for reason in result["manual_review_reasons"]))

    def test_program_eligibility_never_claims_official_qualification(self):
        result = evaluate_program_eligibility(
            {"name": "新闻学", "total_credits": 3, "required_math": False},
            [{"course": "新闻采访与写作", "credits": 3}],
            [{"course_name": "新闻采访与写作", "credits": 3, "status": "completed"}],
        )
        self.assertTrue(result["estimated_eligible"])
        self.assertTrue(result["requires_manual_review"])
        self.assertTrue(any("最终资格" in reason for reason in result["manual_review_reasons"]))

    def test_learning_activity_keeps_date_and_duration(self):
        activity = LearningActivity(
            user_id="00000000-0000-0000-0000-000000000001",
            activity_date=date(2026, 9, 5),
            minutes=45,
            source="manual",
        )
        self.assertEqual(activity.activity_date, date(2026, 9, 5))
        self.assertEqual(activity.minutes, 45)

    def test_learning_activity_summary_counts_days_and_streak(self):
        activities = [
            LearningActivity(activity_date=date(2026, 9, 5), minutes=30),
            LearningActivity(activity_date=date(2026, 9, 4), minutes=20),
            LearningActivity(activity_date=date(2026, 9, 2), minutes=10),
        ]
        summary = account._summarize_learning_activities(activities, today=date(2026, 9, 5))
        self.assertEqual(summary, {"learning_days": 3, "streak_days": 2})

    def test_chat_request_keeps_knowledge_point_context(self):
        request = ChatRequest(
            message="请解释这个知识点",
            intent="tutor",
            knowledge_node_id="k003",
            knowledge_node_name="消息与通讯写作",
        )
        self.assertEqual(request.knowledge_node_id, "k003")
        self.assertEqual(request.knowledge_node_name, "消息与通讯写作")

    def test_schedule_conflict_detector_finds_overlapping_classes(self):
        result = detect_schedule_conflicts(
            [
                {"id": "a", "name": "课程 A", "campus": "仙林校区", "schedule": [{"day": 2, "start": 5, "end": 7}]},
                {"id": "b", "name": "课程 B", "campus": "鼓楼校区", "schedule": [{"day": 2, "start": 7, "end": 8}]},
                {"id": "c", "name": "课程 C", "campus": "鼓楼校区", "schedule": [{"day": 3, "start": 5, "end": 7}]},
            ],
            user_campus="仙林校区",
            campus_flexibility=False,
        )
        self.assertEqual(len(result["conflicts"]), 0)
        self.assertTrue(result["warnings"])

        overlap = detect_schedule_conflicts(
            [
                {"id": "a", "name": "课程 A", "campus": "仙林校区", "schedule": [{"day": 2, "start": 5, "end": 7}]},
                {"id": "b", "name": "课程 B", "campus": "仙林校区", "schedule": [{"day": 2, "start": 6, "end": 8}]},
            ]
        )
        self.assertEqual(len(overlap["conflicts"]), 1)
        self.assertFalse(overlap["feasible"])

    def test_recommendation_contains_explainable_rule_reasons(self):
        result = recommend(
            {
                "major": "新闻学",
                "grade": "大二",
                "campus": "仙林校区",
                "interests": ["数据分析"],
                "career_goals": "数据新闻",
                "math_willingness": True,
                "campus_flexibility": True,
                "credit_budget": 50,
            },
            [{
                "name": "新闻学",
                "total_credits": 45,
                "campus": "仙林校区",
                "subject_rank": "A",
                "core_courses": ["数据新闻"],
                "required_math": False,
                "required_math_level": "",
                "semesters_needed": 4,
                "discipline": "文学",
            }],
        )
        self.assertTrue(result)
        self.assertTrue(result[0]["explanation"])


if __name__ == "__main__":
    unittest.main()
