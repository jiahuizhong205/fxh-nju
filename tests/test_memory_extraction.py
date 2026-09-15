import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from apps.api.config import settings
from services.memory.extraction import build_extraction_messages, extract_memory_candidates
from services.memory.security import sanitize_memory_text
from tests.memory_query_cases import REJECTED_QUERY_URLS, SAFE_QUERY_URLS


class _StaticModel:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.payload)


def _candidate(**overrides):
    value = {
        "category": "study_constraint",
        "content": "我更喜欢仙林校区的下午课程",
        "canonical_key": "campus_time",
        "importance": 0.8,
        "confidence": 0.9,
        "explicitly_requested": False,
        "evidence": "我更喜欢仙林校区的下午课程",
    }
    value.update(overrides)
    return value


class MemoryExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_mock_extracts_stable_preference(self):
        candidates = await extract_memory_candidates(
            "我更喜欢仙林校区的下午课程", mock=True,
        )
        self.assertEqual(candidates[0].category, "study_constraint")
        self.assertIn("仙林校区", candidates[0].content)
        self.assertTrue(candidates[0].canonical_key.startswith("study_constraint:"))

    async def test_mock_keeps_first_person_preference_that_mentions_friends(self):
        candidates = await extract_memory_candidates("我不喜欢交朋友", mock=True)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].category, "interest_strength")

    async def test_mock_result_is_deterministic(self):
        first = await extract_memory_candidates("我更喜欢仙林校区的下午课程", mock=True)
        second = await extract_memory_candidates("我更喜欢仙林校区的下午课程", mock=True)
        self.assertEqual(first, second)

    async def test_credentials_are_never_memorized_even_when_explicit(self):
        for message in (
            "请记住我的验证码是 123456",
            "请记住我的密码是 correct horse battery staple",
            "请记住 access_token=sk-secret-value",
        ):
            with self.subTest(message=message):
                candidates = await extract_memory_candidates(message, mock=True)
                self.assertEqual(candidates, [])

    async def test_contact_requires_explicit_request(self):
        implicit = await extract_memory_candidates("我的手机号是 13800138000", mock=True)
        explicit = await extract_memory_candidates("请记住我的手机号是 13800138000", mock=True)
        self.assertEqual(implicit, [])
        self.assertEqual(len(explicit), 1)
        self.assertTrue(explicit[0].explicitly_requested)

    async def test_negated_memory_request_never_counts_as_explicit_consent(self):
        for message in (
            "请不要记住我的手机号是 13800138000",
            "别保存我的手机号 13800138000",
            "do not remember 我的手机号 13800138000",
            "never save this: 我的手机号 13800138000",
            "请不要记住我更喜欢仙林校区的下午课程",
            "do not remember 我更喜欢仙林校区的下午课程",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    await extract_memory_candidates(message, mock=True),
                    [],
                )

    async def test_identity_financial_and_health_require_explicit_request(self):
        messages = (
            "我的身份证号是 110101199001011234",
            "我的姓名是王小明",
            "我的生日是 2000 年 1 月 1 日",
            "我的银行卡号是 6222021234567890123",
            "我患有哮喘",
            "我的血型是 O 型",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(
                    await extract_memory_candidates(message, mock=True),
                    [],
                )
                self.assertEqual(
                    len(await extract_memory_candidates(f"请记住，{message}", mock=True)),
                    1,
                )

    async def test_real_result_normalizes_safe_whitespace_after_verbatim_validation(self):
        content = ("我  更喜欢仙林校区的下午课程，\n且长期选择下午 " + "安排 " * 80).rstrip()
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                content=content,
                canonical_key="  CAMPUS TIME  ",
                evidence=content,
            )],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            content,
            mock=False,
            model=model,
        )

        self.assertEqual(len(candidates), 1)
        self.assertLessEqual(len(candidates[0].content), 500)
        self.assertEqual(candidates[0].content, " ".join(content.split()))
        self.assertEqual(candidates[0].evidence, content)
        self.assertNotIn("  ", candidates[0].content)
        self.assertEqual(candidates[0].canonical_key, "study_constraint:campus-time")

    async def test_mock_normalizes_whitespace_after_source_validation(self):
        source = "我  更喜欢仙林校区的\n下午课程"

        candidates = await extract_memory_candidates(source, mock=True)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].content, "我 更喜欢仙林校区的 下午课程")
        self.assertEqual(candidates[0].evidence, source)

    async def test_normal_candidate_must_meet_configured_confidence_threshold(self):
        model = _StaticModel(json.dumps({
            "memories": [_candidate(confidence=0.69)],
        }, ensure_ascii=False))
        with patch.object(settings, "memory_capture_confidence_threshold", 0.70):
            candidates = await extract_memory_candidates(
                "我更喜欢仙林校区的下午课程", mock=False, model=model,
            )
        self.assertEqual(candidates, [])

    async def test_malformed_or_failed_real_response_returns_empty_list(self):
        for model in (
            _StaticModel("not json"),
            _StaticModel(json.dumps({"memories": [_candidate(category="other")]})),
            _StaticModel(error=TimeoutError("provider timeout")),
        ):
            with self.subTest(payload=model.payload, error=model.error):
                candidates = await extract_memory_candidates(
                    "我更喜欢仙林校区的下午课程", mock=False, model=model,
                )
                self.assertEqual(candidates, [])

    async def test_schema_rejects_more_than_eight_model_candidates(self):
        model = _StaticModel(json.dumps({
            "memories": [_candidate(canonical_key=f"campus-{index}") for index in range(9)],
        }, ensure_ascii=False))
        candidates = await extract_memory_candidates(
            "我更喜欢仙林校区的下午课程", mock=False, model=model,
        )
        self.assertEqual(candidates, [])

    async def test_model_cannot_hide_source_sensitivity_by_returning_only_the_value(self):
        cases = (
            ("请记住我的验证码是 123456", "123456", True),
            ("我的银行卡号是 6222021234567890123", "6222021234567890123", False),
            ("请记住 abcde12345 " + "无" * 600 + " access token", "abcde12345", True),
        )
        for user_message, content, model_claimed_explicit in cases:
            with self.subTest(user_message=user_message):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        category="confirmed_plan",
                        content=content,
                        canonical_key="private-value",
                        explicitly_requested=model_claimed_explicit,
                    )],
                }, ensure_ascii=False))
                candidates = await extract_memory_candidates(
                    user_message, mock=False, model=model,
                )
                self.assertEqual(candidates, [])

    async def test_assistant_text_cannot_create_unsupported_memory(self):
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="program_preference",
                content="计划辅修新闻学",
                canonical_key="minor",
            )],
        }, ensure_ascii=False))
        candidates = await extract_memory_candidates(
            "谢谢", assistant_message="你计划辅修新闻学", mock=False, model=model,
        )
        self.assertEqual(candidates, [])
        self.assertIn("你计划辅修新闻学", model.messages[-1].content)

    async def test_common_token_overlap_is_not_user_evidence_for_assistant_claim(self):
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="career_goal",
                content="career in AI",
                canonical_key="ai-career",
                evidence="career in AI",
            )],
        }))
        candidates = await extract_memory_candidates(
            "What does a career in AI involve?",
            assistant_message="You plan a career in AI.",
            mock=False,
            model=model,
        )
        self.assertEqual(candidates, [])

    async def test_real_candidate_requires_exact_user_evidence_support(self):
        valid = _StaticModel(json.dumps({
            "memories": [_candidate(
                content="我更喜欢仙林校区的下午课程",
                evidence="我更喜欢仙林校区的下午课程",
            )],
        }, ensure_ascii=False))
        missing = _StaticModel(json.dumps({
            "memories": [_candidate(evidence="")],
        }, ensure_ascii=False))
        hallucinated = _StaticModel(json.dumps({
            "memories": [_candidate(evidence="用户住在鼓楼校区")],
        }, ensure_ascii=False))

        accepted = await extract_memory_candidates(
            "我更喜欢仙林校区的下午课程", mock=False, model=valid,
        )
        self.assertEqual(len(accepted), 1)
        for model in (missing, hallucinated):
            with self.subTest(payload=model.payload):
                self.assertEqual(
                    await extract_memory_candidates(
                        "我更喜欢仙林校区的下午课程", mock=False, model=model,
                    ),
                    [],
                )

    async def test_real_evidence_cannot_drop_negation_qualifiers(self):
        cases = (
            ("我不打算辅修新闻学", "辅修新闻学"),
            ("我没打算辅修新闻学", "打算辅修新闻学"),
            ("我尚未决定辅修新闻学", "决定辅修新闻学"),
            ("我并非更喜欢仙林校区", "更喜欢仙林校区"),
            ("我并非不喜欢新闻学", "不喜欢新闻学"),
            ("I do not plan to minor in journalism", "plan to minor in journalism"),
            ("I never prefer afternoon classes", "prefer afternoon classes"),
        )
        for evidence, content in cases:
            with self.subTest(evidence=evidence):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        category="program_preference",
                        content=content,
                        canonical_key="minor",
                        evidence=evidence,
                    )],
                }, ensure_ascii=False))
                self.assertEqual(
                    await extract_memory_candidates(
                        evidence, mock=False, model=model,
                    ),
                    [],
                )

    async def test_real_evidence_cannot_drop_conditional_qualifiers(self):
        cases = (
            ("如果课程在仙林校区，我才考虑下午上课", "考虑下午上课"),
            ("如果课程在仙林校区，我才下午上课", "才下午上课"),
            ("If classes are online, I prefer afternoons", "I prefer afternoons"),
        )
        for user_message, shortened_content in cases:
            for returned_evidence in (user_message, shortened_content):
                with self.subTest(
                    user_message=user_message,
                    returned_evidence=returned_evidence,
                ):
                    model = _StaticModel(json.dumps({
                        "memories": [_candidate(
                            content=shortened_content,
                            evidence=returned_evidence,
                        )],
                    }, ensure_ascii=False))
                    self.assertEqual(
                        await extract_memory_candidates(
                            user_message, mock=False, model=model,
                        ),
                        [],
                    )

    async def test_real_evidence_accepts_content_that_retains_negation(self):
        evidence = "我不打算辅修新闻学"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="program_preference",
                content=evidence,
                canonical_key="minor",
                evidence=evidence,
            )],
        }, ensure_ascii=False))
        candidates = await extract_memory_candidates(
            evidence, mock=False, model=model,
        )
        self.assertEqual(len(candidates), 1)
        self.assertIn("不打算", candidates[0].content)

    async def test_real_evidence_requires_complete_verbatim_clause(self):
        cases = (
            (
                "When classes are online, I prefer afternoons",
                "I prefer afternoons",
            ),
            (
                "I wouldn't choose morning classes",
                "choose morning classes",
            ),
            (
                "只要课程在仙林校区，我就选择下午上课",
                "选择下午上课",
            ),
            (
                "课程在线时，我更喜欢下午上课",
                "我更喜欢下午上课",
            ),
            (
                "I hardly ever choose morning classes",
                "choose morning classes",
            ),
        )
        for user_message, shortened_content in cases:
            for returned_evidence in (user_message, shortened_content):
                with self.subTest(
                    user_message=user_message,
                    returned_evidence=returned_evidence,
                ):
                    model = _StaticModel(json.dumps({
                        "memories": [_candidate(
                            content=shortened_content,
                            evidence=returned_evidence,
                        )],
                    }, ensure_ascii=False))
                    self.assertEqual(
                        await extract_memory_candidates(
                            user_message, mock=False, model=model,
                        ),
                        [],
                    )

    async def test_real_provider_uses_same_stability_gate_as_mock(self):
        for message in (
            "请记住我的朋友喜欢下午上课",
            "请记住我今天喜欢下午上课",
            "请记住我是不是喜欢下午上课？",
            "请记住新闻学辅修是长期计划",
            "Please remember my mother prefers afternoon classes",
            "Please remember I prefer afternoon classes this semester",
        ):
            with self.subTest(message=message):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        content=message,
                        evidence=message,
                        explicitly_requested=True,
                    )],
                }, ensure_ascii=False))
                self.assertEqual(
                    await extract_memory_candidates(
                        message, mock=False, model=model,
                    ),
                    [],
                )

    async def test_sensitive_consent_is_scoped_to_candidate_sentence(self):
        user_message = "请记住我长期偏好下午课程。我的手机号是 13800138000。"
        evidence = "我的手机号是 13800138000。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="confirmed_plan",
                content=evidence,
                evidence=evidence,
                confidence=0.9,
            )],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            user_message, mock=False, model=model,
        )

        self.assertEqual(candidates, [])

    async def test_sensitive_candidate_accepts_consent_in_its_own_sentence(self):
        user_message = "我长期偏好下午课程。请记住我的手机号是 13800138000。"
        evidence = "请记住我的手机号是 13800138000。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="confirmed_plan",
                content=evidence,
                evidence=evidence,
                confidence=0.9,
            )],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            user_message, mock=False, model=model,
        )

        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].explicitly_requested)

    async def test_explicit_confidence_relaxation_is_scoped_to_candidate_sentence(self):
        user_message = "请记住我长期偏好下午课程。我的长期目标是完成新闻学辅修。"
        evidence = "我的长期目标是完成新闻学辅修。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="learning_goal",
                content=evidence,
                evidence=evidence,
                confidence=0.55,
            )],
        }, ensure_ascii=False))

        with patch.object(settings, "memory_capture_confidence_threshold", 0.70):
            candidates = await extract_memory_candidates(
                user_message, mock=False, model=model,
            )

        self.assertEqual(candidates, [])

    async def test_negated_intent_does_not_cross_sentence_boundary(self):
        user_message = "请不要记住我喜欢上午课程。我长期偏好下午课程。"
        evidence = "我长期偏好下午课程。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(content=evidence, evidence=evidence)],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            user_message, mock=False, model=model,
        )

        self.assertEqual(len(candidates), 1)
        self.assertFalse(candidates[0].explicitly_requested)

    async def test_mock_applies_consent_and_negation_per_sentence(self):
        sensitive = await extract_memory_candidates(
            "请记住我长期偏好下午课程。我的手机号是 13800138000。",
            mock=True,
        )
        after_negation = await extract_memory_candidates(
            "请不要记住我喜欢上午课程。我长期偏好下午课程。",
            mock=True,
        )

        self.assertEqual(len(sensitive), 1)
        self.assertNotIn("手机号", sensitive[0].content)
        self.assertEqual(len(after_negation), 1)
        self.assertIn("下午课程", after_negation[0].content)

    async def test_mock_scopes_consent_across_cjk_ascii_period_boundary(self):
        candidates = await extract_memory_candidates(
            "请记住我长期偏好下午课程.我的手机号是 13800138000。",
            mock=True,
        )

        self.assertEqual(len(candidates), 1)
        self.assertIn("下午课程", candidates[0].content)
        self.assertNotIn("手机号", candidates[0].content)

    async def test_real_provider_scopes_consent_across_cjk_ascii_period_boundary(self):
        user_message = "请记住我长期偏好下午课程.我的手机号是 13800138000。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="confirmed_plan",
                content=user_message,
                evidence=user_message,
                explicitly_requested=True,
            )],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            user_message, mock=False, model=model,
        )

        self.assertEqual(candidates, [])

    async def test_mock_scopes_consent_after_decimal_or_url_sentence(self):
        for user_message in (
            "请记住我长期偏好下午课程，GPA 目标 3.8.我的手机号是 13800138000。",
            "请记住我长期偏好下午课程，参考 https://example.com.我的手机号是 13800138000。",
            "请记住我长期偏好下午课程，参考 https://example.com/path. 我的手机号是 13800138000。",
        ):
            with self.subTest(user_message=user_message):
                candidates = await extract_memory_candidates(user_message, mock=True)
                self.assertEqual(len(candidates), 1)
                self.assertIn("下午课程", candidates[0].content)
                self.assertNotIn("手机号", candidates[0].content)

    async def test_real_provider_scopes_consent_after_decimal_or_url_sentence(self):
        for user_message in (
            "请记住我长期偏好下午课程，GPA 目标 3.8.我的手机号是 13800138000。",
            "请记住我长期偏好下午课程，参考 https://example.com.我的手机号是 13800138000。",
            "请记住我长期偏好下午课程，参考 https://example.com/path. 我的手机号是 13800138000。",
        ):
            with self.subTest(user_message=user_message):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        category="confirmed_plan",
                        content=user_message,
                        evidence=user_message,
                        explicitly_requested=True,
                    )],
                }, ensure_ascii=False))

                candidates = await extract_memory_candidates(
                    user_message, mock=False, model=model,
                )

                self.assertEqual(candidates, [])

    async def test_cjk_url_and_email_periods_remain_inside_token_spans(self):
        cases = (
            "请记住我长期偏好下午课程，参考 https://example.com/path",
            "请记住我长期偏好下午课程，参考 https://example.com/path.v1",
            "请记住我长期偏好下午课程，参考 https://例子.公司/课程",
            "请记住我的邮箱是 用户@例子.公司",
        )
        for evidence in cases:
            with self.subTest(evidence=evidence, mode="mock"):
                candidates = await extract_memory_candidates(evidence, mock=True)
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].evidence, evidence)

            with self.subTest(evidence=evidence, mode="provider"):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        content=evidence,
                        evidence=evidence,
                        explicitly_requested=True,
                    )],
                }, ensure_ascii=False))
                candidates = await extract_memory_candidates(
                    evidence, mock=False, model=model,
                )
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].evidence, evidence)

    async def test_ambiguous_dotted_token_boundary_fails_closed_in_mock(self):
        for user_message in (
            "请记住我长期偏好下午课程，参考 https://example.com/path.我的手机号是 13800138000。",
            "请记住我的邮箱是 用户@例子.公司.我的手机号是 13800138000。",
            "请记住我长期偏好下午课程，参考 https://例子.公司/课程.我的手机号是 13800138000。",
        ):
            with self.subTest(user_message=user_message):
                self.assertEqual(
                    await extract_memory_candidates(user_message, mock=True),
                    [],
                )

    async def test_ambiguous_dotted_token_boundary_skips_real_provider(self):
        for user_message in (
            "请记住我长期偏好下午课程，参考 https://example.com/path.我的手机号是 13800138000。",
            "请记住我的邮箱是 用户@例子.公司.我的手机号是 13800138000。",
            "请记住我长期偏好下午课程，参考 https://例子.公司/课程.我的手机号是 13800138000。",
        ):
            with self.subTest(user_message=user_message):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        category="confirmed_plan",
                        content=user_message,
                        evidence=user_message,
                        explicitly_requested=True,
                    )],
                }, ensure_ascii=False))

                self.assertEqual(
                    await extract_memory_candidates(
                        user_message, mock=False, model=model,
                    ),
                    [],
                )
                self.assertIsNone(model.messages)

    async def test_full_jwt_fails_closed_before_mock_or_provider_extraction(self):
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        user_message = f"我长期偏好下午课程。请记住我的值是 {jwt}。"
        evidence = "我长期偏好下午课程。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(content=evidence, evidence=evidence)],
        }, ensure_ascii=False))

        self.assertEqual(
            await extract_memory_candidates(user_message, mock=True),
            [],
        )
        self.assertEqual(
            await extract_memory_candidates(user_message, mock=False, model=model),
            [],
        )
        self.assertIsNone(model.messages)

    async def test_common_token_families_and_high_entropy_values_skip_provider(self):
        secrets = (
            "xoxp-111111111111-222222222222-AbCdEfGhIjKlMnOp",
            "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
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
        for secret in secrets:
            with self.subTest(secret=secret):
                user_message = f"请记住我的长期计划和这个值 {secret}"
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        content=user_message,
                        evidence=user_message,
                        explicitly_requested=True,
                    )],
                }, ensure_ascii=False))
                self.assertEqual(
                    await extract_memory_candidates(
                        user_message, mock=False, model=model,
                    ),
                    [],
                )
                self.assertIsNone(model.messages)

    async def test_url_userinfo_and_invalid_netloc_fail_closed_before_provider(self):
        unsafe_sources = (
            "Please remember I prefer https://alice:hunter2@example.com/course",
            "Please remember I prefer https://alice:x@example.com/course",
            "Please remember I prefer https://alice:hunter2＠example.com/path",
            *(f"Please remember I prefer {url}" for url in REJECTED_QUERY_URLS),
        )
        for source in unsafe_sources:
            with self.subTest(source=source):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        category="interest_strength",
                        content=source,
                        evidence=source,
                        explicitly_requested=True,
                    )],
                }, ensure_ascii=False))
                self.assertEqual(
                    await extract_memory_candidates(
                        source, mock=False, model=model,
                    ),
                    [],
                )
                self.assertIsNone(model.messages)

    async def test_urls_and_course_slugs_are_eligible_for_automatic_extraction(self):
        safe_sources = (
            "I prefer course material at https://github.com/openai/openai-python/issues/1234",
            "I prefer course material at https://token.example.com/course",
            "I prefer course material at https://example.com/token-economics/",
            "I prefer the CS2026-Interdisciplinary-Course-Planning track",
        )
        for source in safe_sources:
            with self.subTest(source=source):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        category="interest_strength",
                        content=source,
                        evidence=source,
                    )],
                }, ensure_ascii=False))
                candidates = await extract_memory_candidates(
                    source, mock=False, model=model,
                )
                self.assertEqual([candidate.content for candidate in candidates], [source])
                self.assertIsNotNone(model.messages)

    async def test_safe_encoded_query_does_not_block_real_extraction(self):
        evidence = "我长期偏好下午课程。"
        for url in SAFE_QUERY_URLS:
            with self.subTest(url=url):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(content=evidence, evidence=evidence)],
                }, ensure_ascii=False))
                candidates = await extract_memory_candidates(
                    f"{evidence} 参考 {url}", mock=False, model=model,
                )
                self.assertEqual([candidate.content for candidate in candidates], [evidence])
                self.assertIsNotNone(model.messages)

    async def test_sentence_splitter_preserves_internal_english_periods(self):
        cases = (
            "我的长期目标是 GPA 达到 3.8。",
            "I prefer resources from https://example.com/path.",
            "请记住我的邮箱是 student@example.com。",
        )
        for evidence in cases:
            with self.subTest(evidence=evidence):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(content=evidence, evidence=evidence)],
                }, ensure_ascii=False))
                candidates = await extract_memory_candidates(
                    evidence, mock=False, model=model,
                )
                self.assertEqual(len(candidates), 1)
                self.assertEqual(candidates[0].evidence, evidence)

    async def test_consecutive_terminal_marks_remain_one_question_sentence(self):
        cases = (
            ("我喜欢仙林校区下午课程！？", "我喜欢仙林校区下午课程！"),
            ("I prefer afternoon classes?!", "I prefer afternoon classes?"),
            ("我喜欢仙林校区下午课程……？", "我喜欢仙林校区下午课程……？"),
        )
        for user_message, provider_fragment in cases:
            with self.subTest(user_message=user_message):
                model = _StaticModel(json.dumps({
                    "memories": [_candidate(
                        content=provider_fragment,
                        evidence=provider_fragment,
                    )],
                }, ensure_ascii=False))
                self.assertEqual(
                    await extract_memory_candidates(user_message, mock=True),
                    [],
                )
                self.assertEqual(
                    await extract_memory_candidates(
                        user_message, mock=False, model=model,
                    ),
                    [],
                )

    async def test_mock_returns_at_most_eight_candidates_in_source_order(self):
        user_message = "".join(
            f"我长期偏好第 {index} 门下午课程。" for index in range(9)
        )

        candidates = await extract_memory_candidates(user_message, mock=True)

        self.assertEqual(len(candidates), 8)
        for index, candidate in enumerate(candidates):
            self.assertIn(f"第 {index} 门", candidate.content)

    async def test_real_evidence_accepts_complete_verbatim_stable_clause(self):
        evidence = (
            "When choosing courses, I consistently prefer afternoon classes"
        )
        model = _StaticModel(json.dumps({
            "memories": [_candidate(content=evidence, evidence=evidence)],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            evidence, mock=False, model=model,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].content, evidence)

    async def test_real_evidence_accepts_a_complete_punctuated_sentence(self):
        user_message = "我长期偏好下午课程。我的目标是完成新闻学辅修。"
        evidence = "我长期偏好下午课程。"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(content=evidence, evidence=evidence)],
        }, ensure_ascii=False))

        candidates = await extract_memory_candidates(
            user_message, mock=False, model=model,
        )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].content, evidence)

    async def test_mock_rejects_questions_third_party_and_temporary_context(self):
        for message in (
            "我更喜欢仙林校区的下午课程吗？",
            "我是不是更喜欢仙林校区的下午课程",
            "我的室友更喜欢仙林校区的下午课程",
            "我的妈妈更喜欢仙林校区的下午课程",
            "他更喜欢仙林校区的下午课程",
            "我今天下午在仙林校区上课",
            "我这学期下午在仙林校区上课",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    await extract_memory_candidates(message, mock=True),
                    [],
                )

    async def test_mock_allows_affirmative_explicit_request_for_stable_content(self):
        candidates = await extract_memory_candidates(
            "请记住新闻学辅修是我的长期计划", mock=True,
        )
        self.assertEqual(len(candidates), 1)
        self.assertTrue(candidates[0].explicitly_requested)

    async def test_mock_explicit_request_does_not_bypass_source_stability(self):
        for message in (
            "请记住新闻学辅修是长期计划",
            "请记住我的朋友喜欢仙林校区的下午课程",
            "请记住我今天下午在仙林校区上课",
            "请记住我是不是更喜欢仙林校区的下午课程？",
            "请记住我有没有更喜欢仙林校区的下午课程",
            "我的哥哥喜欢仙林校区的下午课程",
            "我的父亲喜欢仙林校区的下午课程",
            "我的孩子喜欢仙林校区的下午课程",
            "我最近下午在仙林校区上课",
            "我目前下午在仙林校区上课",
            "我现在下午在仙林校区上课",
            "我这一周下午在仙林校区上课",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    await extract_memory_candidates(message, mock=True),
                    [],
                )

    async def test_default_mode_uses_single_mock_llm_setting(self):
        with patch.object(settings, "mock_llm", True):
            candidates = await extract_memory_candidates("我计划辅修新闻学")
        self.assertEqual(len(candidates), 1)


class MemorySecurityTests(unittest.TestCase):
    def test_query_percent_decoding_stops_after_one_layer(self):
        for query in (
            "%2574%256f%256b%2565%256e%253Dhunter2",
            "value=%2573%256b%252Dshortsecret",
            "value=bearer%2Bshortsecret",
        ):
            source = f"https://example.com/course?{query}"
            with self.subTest(query=query):
                self.assertEqual(
                    sanitize_memory_text(source, explicitly_requested=True), source,
                )

    def test_sanitizer_normalizes_and_caps_text(self):
        sanitized = sanitize_memory_text("  仙林校区\r\n  下午课程  " + "甲" * 600)
        self.assertTrue(sanitized.startswith("仙林校区 下午课程"))
        self.assertLessEqual(len(sanitized), 500)

    def test_sanitizer_rejects_secrets_even_when_explicit(self):
        for secret in (
            "验证码 123456",
            "password is hunter2",
            "my password hunter2",
            "API key is highly-secret",
            "token is session-secret",
            "token session-secret",
            "client_secret=client-secret-value",
            "client secret is client-secret-value",
            "secret key: secret-value",
            "private key: private-value",
            "4a7d1ed414474e4033ac29ccb8653d9b7e0c1a59f2d4b6c8e0a1c3d5f7b9e2a4",
            "https://alice:hunter2@example.com/course",
            "https://alice:x@example.com/course",
            "https://alice:hunter2＠example.com/path",
            "https://exam_ple.com/course",
            "https://example.com/reset/Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "https://example.com/reset/4a7d1ed414474e4033ac29ccb8653d9b7e0c1a59f2d4b6c8e0a1c3d5f7b9e2a4",
            "https://example.com/reset?token=Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "https://example.com/reset?value=Q7vN4%5FcM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "https://example.com/reset#Q7vN4_cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
            "aB3dE5fG7hI9jK1lM2nO4pQ6rS8tU0vW3xY5zA7bC9dE",
            "A8fK2mP7qR4sT9vW3xY6zB1cD5eF8gH2jL4nO7pQ9rS6tUV2",
            "客户端密钥是 client-secret-value",
            "请保存这个密钥 secret-value",
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
            "sk-proj-abcdefghijklmnopqrstuvwxyz",
            "-----BEGIN PRIVATE KEY----- ABCDEF -----END PRIVATE KEY-----",
        ):
            with self.subTest(secret=secret):
                self.assertEqual(
                    sanitize_memory_text(secret, explicitly_requested=True),
                    "",
                )

    def test_high_entropy_guard_does_not_reject_ordinary_language_or_uuids(self):
        safe_values = (
            "I consistently prefer interdisciplinary afternoon courses",
            "我长期偏好仙林校区的跨学科下午课程",
            "课程记录 ID 是 550e8400-e29b-41d4-a716-446655440000",
            "参考 https://example.com/interdisciplinary-courses",
            "课程资料在 https://github.com/openai/openai-python/issues/1234",
            "课程资料在 https://[2001:db8::1]:443/token-economics/",
            "课程资料在 https://token.example.com/course",
            "课程资料在 https://example.com/token-economics/",
            "I prefer the CS2026-Interdisciplinary-Course-Planning track",
        )
        for value in safe_values:
            with self.subTest(value=value):
                self.assertEqual(
                    sanitize_memory_text(value, explicitly_requested=True),
                    value,
                )

    def test_real_extraction_rejects_authentication_secret_candidates(self):
        secret = "客户端密钥是 client-secret-value"
        evidence = f"请记住我的{secret}"
        model = _StaticModel(json.dumps({
            "memories": [_candidate(
                category="confirmed_plan",
                content=evidence,
                canonical_key="secret",
                evidence=evidence,
                explicitly_requested=True,
            )],
        }, ensure_ascii=False))
        candidates = self._run_async(extract_memory_candidates(
            evidence, mock=False, model=model,
        ))
        self.assertEqual(candidates, [])

    def test_real_extraction_prompt_forbids_all_authentication_secret_classes(self):
        prompt = build_extraction_messages("普通消息", "")[0].content.lower()
        for term in ("认证秘密", "client secret", "private key", "pem"):
            with self.subTest(term=term):
                self.assertIn(term, prompt)

    def test_sanitizer_gates_sensitive_text(self):
        self.assertEqual(sanitize_memory_text("手机号 13800138000"), "")
        self.assertEqual(
            sanitize_memory_text("手机号 13800138000", explicitly_requested=True),
            "手机号 13800138000",
        )

    @staticmethod
    def _run_async(awaitable):
        import asyncio

        return asyncio.run(awaitable)


if __name__ == "__main__":
    unittest.main()
