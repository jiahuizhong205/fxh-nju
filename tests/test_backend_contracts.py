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
from apps.api.models import User
from apps.api.routes import auth
from apps.api.routes import preferences


class _CommitOnlyDb:
    """change_password 当前只需要验证提交动作的最小 fake session。"""

    def __init__(self):
        self.commit_count = 0

    async def commit(self):
        self.commit_count += 1


class BackendContractTests(unittest.TestCase):
    def test_mock_llm_is_safe_by_default(self):
        self.assertTrue(config.Settings(_env_file=None).mock_llm)

    def test_compose_explicitly_defaults_to_mock(self):
        compose = Path(__file__).parents[1] / "infra" / "compose" / "docker-compose.yml"
        content = compose.read_text(encoding="utf-8")
        self.assertIn("MOCK_LLM: ${MOCK_LLM:-true}", content)

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


if __name__ == "__main__":
    unittest.main()
