"""Schema-validated, privacy-filtered long-term memory extraction."""

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from apps.api.config import settings
from services.agent_runtime.llm import create_chat_model
from services.memory.security import (
    Sensitivity,
    classify_memory_sensitivity,
    has_explicit_memory_intent,
    has_negated_memory_intent,
    normalize_memory_text,
    sanitize_memory_text,
)


MemoryCategory = Literal[
    "learning_goal",
    "program_preference",
    "interest_strength",
    "study_constraint",
    "career_goal",
    "confirmed_plan",
]


class MemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory
    content: str = Field(min_length=1, max_length=500)
    canonical_key: str = Field(min_length=1, max_length=300)
    importance: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    explicitly_requested: StrictBool = False
    evidence: str = Field(default="", max_length=500)


class MemoryExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memories: list[MemoryCandidate] = Field(default_factory=list, max_length=8)


_CATEGORY_RULES: tuple[tuple[MemoryCategory, tuple[str, ...]], ...] = (
    ("study_constraint", ("校区", "上午", "下午", "晚上", "周末", "上课时间", "课程时间", "不能上课", "线上课", "线下课")),
    ("program_preference", ("辅修", "专业", "培养方案", "项目偏好", "课程偏好")),
    ("career_goal", ("职业", "实习", "就业", "求职", "工作岗位", "职位")),
    ("learning_goal", ("想学", "学习目标", "掌握", "提升", "学会")),
    ("confirmed_plan", ("计划", "决定", "已选", "报名", "准备")),
    ("interest_strength", ("感兴趣", "喜欢", "偏爱", "不喜欢")),
)
_KEY_HINTS = (
    ("campus", ("校区",)),
    ("schedule", ("上午", "下午", "晚上", "周末", "时间")),
    ("minor", ("辅修",)),
    ("major", ("专业",)),
    ("internship", ("实习",)),
    ("career", ("职业", "就业", "求职", "岗位", "职位")),
    ("health", ("健康", "病", "症", "过敏", "血型", "哮喘")),
    ("financial", ("银行", "信用卡", "收入", "工资", "薪资", "负债")),
    ("identity", ("身份证", "护照", "姓名", "名字", "出生", "生日", "住址", "地址")),
    ("contact", ("手机", "电话", "邮箱", "邮件", "微信", "QQ")),
)
_EXPLICIT_PREFIX_RE = re.compile(
    r"^\s*(?:(?:请|麻烦|帮我)?(?:记住|记下|记一下|保存|存下|留存)"
    r"|(?:please\s+)?remember|save\s+(?:this|that|it))\s*[，,：:]?\s*",
    re.IGNORECASE,
)
_QUESTION_RE = re.compile(
    r"[?？]|(?:吗|么|呢)\s*[。.!！]?$"
    r"|(?:为什么|怎么|如何|什么|是否|能否|可不可以|是不是|有没有|要不要|会不会|可否)"
    r"|^\s*(?:what|why|how|whether|can|could|would|should|is|are|do|does|did)\b",
    re.IGNORECASE,
)
_THIRD_PARTY_RE = re.compile(
    r"(?:^|[，,。.!！?？\s])(?:我(?:的)?)?"
    r"(?:室友|朋友|同学|老师|导师|同事|父母|父亲|母亲|爸爸|妈妈|哥哥|姐姐|弟弟|妹妹|孩子|儿子|女儿|丈夫|妻子|家人)"
    r"|(?:^|[，,。.!！?？\s])(?:他|她|他们|她们)(?:的|更|想|计划|喜欢|偏好|不能|不)"
    r"|\b(?:my\s+(?:roommate|friend|classmate|teacher|colleague|parent|mother|father|"
    r"brother|sister|child|son|daughter|spouse|husband|wife|family|partner|mentor|"
    r"supervisor|manager|boss|teammate)|he|she|they)\b",
    re.IGNORECASE,
)
_TEMPORARY_RE = re.compile(
    r"(?:今天|明天|昨天|这次|本次|刚刚|最近|近来|近期|目前|现在|当下|临时|暂时|本周|下周|这周|这一周|这学期|这一学期|本学期|下学期|本月|这个月|下个月)"
    r"|\b(?:today|tomorrow|yesterday|recently|currently|right now|for now|temporarily|"
    r"this week|next week|this semester|next semester|this month|next month)\b",
    re.IGNORECASE,
)
_FIRST_PERSON_RE = re.compile(r"我(?:的)?|本人|\b(?:i|my|me)\b", re.IGNORECASE)
_NON_PERIOD_SENTENCE_BOUNDARIES = frozenset("。！？!?")
_TERMINAL_MARK_GROUP = frozenset("。！？.!?…")
_CJK_RANGE = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_UNAMBIGUOUS_TOKEN_PATTERNS = (
    # JWTs must stay intact even though the full-source credential guard also
    # rejects them before extraction.
    re.compile(r"\b[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"(?<![\w.])\d+(?:\.\d+)+(?!\d)"),
    re.compile(r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}\b", re.IGNORECASE),
)
_URL_SCHEME_RE = re.compile(r"https?://", re.IGNORECASE)
_ASCII_AUTHORITY_RE = re.compile(
    r"(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}(?::\d+)?",
    re.IGNORECASE,
)
_TOKEN_SCAN_STOPS = frozenset("，。！？!?；;、,\"'“”‘’（）()【】[]{}<>")
_EMAIL_LOCAL_CHAR_RE = re.compile(rf"[A-Za-z0-9._%+\-{_CJK_RANGE}]")
_EMAIL_DOMAIN_CHAR_RE = re.compile(rf"[A-Za-z0-9.\-{_CJK_RANGE}]")


def _is_cjk_character(character: str) -> bool:
    return any(
        start <= ord(character) <= end
        for start, end in (
            (0x3400, 0x4DBF),
            (0x4E00, 0x9FFF),
            (0xF900, 0xFAFF),
            (0x20000, 0x2FA1F),
        )
    )


def _scan_chunk_end(text: str, start: int) -> int:
    end = start
    while (
        end < len(text)
        and not text[end].isspace()
        and text[end] not in _TOKEN_SCAN_STOPS
    ):
        end += 1
    return end


def _period_followed_by_cjk(text: str, index: int, end: int) -> bool:
    return index + 1 < end and _is_cjk_character(text[index + 1])


def _url_token_spans(text: str) -> tuple[tuple[tuple[int, int], ...], bool]:
    """Scan URL structure and flag dots whose ownership is unknowable."""
    spans: list[tuple[int, int]] = []
    ambiguous = False
    for scheme in _URL_SCHEME_RE.finditer(text):
        start = scheme.start()
        host_start = scheme.end()
        raw_end = _scan_chunk_end(text, host_start)
        while raw_end > host_start and text[raw_end - 1] == ".":
            raw_end -= 1
        if raw_end <= host_start:
            continue

        suffix_start = min(
            (
                index
                for marker in "/?#"
                if (index := text.find(marker, host_start, raw_end)) >= 0
            ),
            default=raw_end,
        )
        authority_end = suffix_start
        ascii_authority = _ASCII_AUTHORITY_RE.match(
            text, host_start, authority_end,
        )
        token_end = raw_end

        # An ASCII host has a deterministic TLD boundary. Its immediately
        # following `.中文` is therefore sentence punctuation, not URL text.
        if suffix_start == raw_end and ascii_authority is not None:
            boundary = ascii_authority.end()
            if (
                boundary + 1 < raw_end
                and text[boundary] == "."
                and _is_cjk_character(text[boundary + 1])
            ):
                token_end = boundary

        if suffix_start < raw_end:
            ambiguous = ambiguous or any(
                text[index] == "."
                and _period_followed_by_cjk(text, index, raw_end)
                for index in range(suffix_start, raw_end)
            )
        elif ascii_authority is None:
            authority_periods = [
                index
                for index in range(host_start, token_end)
                if text[index] == "."
            ]
            # One dot is the ordinary two-label IDN case. A later `.中文`
            # could be another IDN label or a new sentence, so reject it.
            ambiguous = ambiguous or any(
                _period_followed_by_cjk(text, index, token_end)
                for index in authority_periods[1:]
            )

        spans.append((start, token_end))
    return tuple(spans), ambiguous


def _email_token_spans(text: str) -> tuple[tuple[tuple[int, int], ...], bool]:
    """Scan Unicode email shapes without letting the domain consume prose."""
    spans: list[tuple[int, int]] = []
    ambiguous = False
    for at_index, character in enumerate(text):
        if character != "@":
            continue
        start = at_index
        while start > 0 and _EMAIL_LOCAL_CHAR_RE.fullmatch(text[start - 1]):
            start -= 1
        raw_end = at_index + 1
        while (
            raw_end < len(text)
            and _EMAIL_DOMAIN_CHAR_RE.fullmatch(text[raw_end])
        ):
            raw_end += 1
        while raw_end > at_index + 1 and text[raw_end - 1] == ".":
            raw_end -= 1
        if start == at_index or raw_end == at_index + 1:
            continue

        domain_start = at_index + 1
        ascii_domain = _ASCII_AUTHORITY_RE.match(text, domain_start, raw_end)
        token_end = raw_end
        if ascii_domain is not None:
            boundary = ascii_domain.end()
            if (
                boundary + 1 < raw_end
                and text[boundary] == "."
                and _is_cjk_character(text[boundary + 1])
            ):
                token_end = boundary
        else:
            domain_periods = [
                index
                for index in range(domain_start, token_end)
                if text[index] == "."
            ]
            ambiguous = ambiguous or any(
                _period_followed_by_cjk(text, index, token_end)
                for index in domain_periods[1:]
            )
        if "." in text[domain_start:token_end]:
            spans.append((start, token_end))
    return tuple(spans), ambiguous


def _token_period_analysis(text: str) -> tuple[frozenset[int], bool]:
    protected: set[int] = set()
    for pattern in _UNAMBIGUOUS_TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            # A conventional trailing full stop is sentence punctuation, not
            # part of a URL-like token.
            while end > start and text[end - 1] in ".,;:":
                end -= 1
            protected.update(
                index for index in range(start, end) if text[index] == "."
            )
    url_spans, ambiguous_url = _url_token_spans(text)
    email_spans, ambiguous_email = _email_token_spans(text)
    for start, end in (*url_spans, *email_spans):
        protected.update(
            index for index in range(start, end) if text[index] == "."
        )
    return frozenset(protected), ambiguous_url or ambiguous_email


def _has_ambiguous_dotted_token_boundary(text: str) -> bool:
    return _token_period_analysis(str(text or ""))[1]


def _protected_period_indexes(text: str) -> frozenset[int]:
    return _token_period_analysis(text)[0]


def _canonical_key(category: MemoryCategory, key: str) -> str:
    normalized = normalize_memory_text(key).lower()
    prefix = f"{category}:"
    if normalized.startswith(prefix):
        normalized = normalized[len(prefix):]
    normalized = normalized.replace(":", "-")
    normalized = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", normalized, flags=re.UNICODE)
    normalized = re.sub(r"-+", "-", normalized).strip("-_") or "general"
    return f"{prefix}{normalized[:max(1, 300 - len(prefix))]}"


def _mock_key(message: str) -> str:
    hints = [key for key, words in _KEY_HINTS if any(word in message for word in words)]
    return "-".join(hints[:2]) or "general"


def _mock_category(message: str, *, sensitive: bool) -> MemoryCategory | None:
    for category, words in _CATEGORY_RULES:
        if any(word in message for word in words):
            return category
    return "confirmed_plan" if sensitive else None


def _is_stable_user_source(source: str) -> bool:
    """Apply one conservative source gate to mock and provider candidates."""
    fact_source = _EXPLICIT_PREFIX_RE.sub("", source)
    return bool(
        _FIRST_PERSON_RE.search(fact_source)
        and not _QUESTION_RE.search(fact_source)
        and not _THIRD_PARTY_RE.search(fact_source)
        and not _TEMPORARY_RE.search(fact_source)
    )


def _source_sentences(source: str) -> tuple[str, ...]:
    """Return trimmed source sentences while preserving their internal text."""
    text = str(source or "")
    protected_periods = _protected_period_indexes(text)
    sentences: list[str] = []
    start = 0
    index = 0
    while index < len(text):
        character = text[index]
        is_period_boundary = (
            character == "."
            and index not in protected_periods
            and (
                index + 1 == len(text)
                or text[index + 1].isspace()
                or _is_cjk_character(text[index + 1])
            )
        )
        if character not in _NON_PERIOD_SENTENCE_BOUNDARIES and not is_period_boundary:
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end] in _TERMINAL_MARK_GROUP:
            end += 1
        sentence = text[start:end].strip()
        if sentence:
            sentences.append(sentence)
        start = end
        index = end
    trailing = text[start:].strip()
    if trailing:
        sentences.append(trailing)
    return tuple(sentences)


def deterministic_candidates(user_message: str) -> list[MemoryCandidate]:
    """Produce stable local candidates without implying semantic model ability."""
    if (
        classify_memory_sensitivity(user_message) == "credential"
        or _has_ambiguous_dotted_token_boundary(user_message)
    ):
        return []
    candidates: list[MemoryCandidate] = []
    for content in _source_sentences(user_message):
        if len(content) > 500 or has_negated_memory_intent(content):
            continue
        explicitly_requested = has_explicit_memory_intent(content)
        sensitivity = classify_memory_sensitivity(content)
        if sensitivity == "credential":
            continue
        if sensitivity == "personal_sensitive" and not explicitly_requested:
            continue
        if not _is_stable_user_source(content):
            continue

        category = _mock_category(content, sensitive=sensitivity == "personal_sensitive")
        if category is None:
            continue
        candidates.append(MemoryCandidate(
            category=category,
            content=content,
            canonical_key=_canonical_key(category, _mock_key(content)),
            importance=0.75,
            confidence=0.90,
            explicitly_requested=explicitly_requested,
            evidence=content,
        ))
        if len(candidates) == 8:
            break
    return candidates


def build_extraction_messages(user_message: str, assistant_message: str):
    from langchain_core.messages import HumanMessage, SystemMessage

    schema = json.dumps(MemoryExtractionResult.model_json_schema(), ensure_ascii=False)
    payload = json.dumps({
        "user_message": user_message,
        "assistant_message_for_disambiguation_only": assistant_message,
    }, ensure_ascii=False, separators=(",", ":"))
    return [
        SystemMessage(content=(
            "提取跨会话仍有用的稳定用户偏好、目标、约束或已确认计划。"
            "只能把 user_message 中有依据的用户信息作为候选；assistant_message 仅可消歧，"
            "不得成为新事实来源。每个候选的 evidence 必须逐字等于 user_message 中的一个完整句子，"
            "包括该句的全部从句、修饰语和标点；content 必须与 evidence 逐字相同。"
            "不得概括、改写、删词或抽取句子的一部分；后续存储层再做规范化。"
            "问句、第三方主体、临时状态以及没有用户第一人称事实的内容都不得提取；"
            "显式记忆请求也不得绕过这些来源要求。"
            "不要提取任何认证秘密，包括密码、"
            "验证码、访问令牌、API key、client secret、secret key、private key、云服务密钥或 PEM 私钥。"
            "只输出符合以下 JSON Schema 的 JSON，不要输出代码围栏或解释：" + schema
        )),
        HumanMessage(content=payload),
    ]


async def request_candidates(model: Any, user_message: str, assistant_message: str) -> list[MemoryCandidate]:
    response = await model.ainvoke(build_extraction_messages(user_message, assistant_message))
    content = response.content
    if isinstance(content, (str, bytes, bytearray)):
        result = MemoryExtractionResult.model_validate_json(content)
    else:
        result = MemoryExtractionResult.model_validate(content)
    return result.memories


def _has_verified_evidence(
    candidate: MemoryCandidate,
    user_message: str,
) -> bool:
    content = candidate.content
    evidence = candidate.evidence
    user = str(user_message or "")
    if not content or not evidence or not user or content != evidence:
        return False
    return evidence in _source_sentences(user) and _is_stable_user_source(evidence)


def validate_and_filter_candidates(
    raw: list[MemoryCandidate],
    user_message: str,
) -> list[MemoryCandidate]:
    if (
        classify_memory_sensitivity(user_message) == "credential"
        or _has_ambiguous_dotted_token_boundary(user_message)
    ):
        return []
    threshold = max(0.0, min(1.0, settings.memory_capture_confidence_threshold))
    accepted: list[MemoryCandidate] = []
    for candidate in raw:
        if not _has_verified_evidence(candidate, user_message):
            continue
        evidence = candidate.evidence
        if has_negated_memory_intent(evidence):
            continue
        explicitly_requested = has_explicit_memory_intent(evidence)
        source_sensitivity = classify_memory_sensitivity(evidence)
        if source_sensitivity == "credential":
            continue
        if source_sensitivity == "personal_sensitive" and not explicitly_requested:
            continue
        content = sanitize_memory_text(
            candidate.content,
            explicitly_requested=explicitly_requested,
        )
        if not content:
            continue
        confidence_threshold = min(threshold, 0.5) if explicitly_requested else threshold
        if candidate.confidence < confidence_threshold:
            continue
        accepted.append(candidate.model_copy(update={
            "content": content,
            "canonical_key": _canonical_key(candidate.category, candidate.canonical_key),
            "explicitly_requested": explicitly_requested,
            "evidence": evidence,
        }))
    return accepted


async def extract_memory_candidates(
    user_message: str,
    *,
    assistant_message: str = "",
    mock: bool | None = None,
    model: Any | None = None,
) -> list[MemoryCandidate]:
    """Extract safe candidates; provider and validation failures degrade to empty."""
    use_mock = settings.mock_llm if mock is None else mock
    try:
        # Scan the intact source before sentence parsing so dotted credentials
        # such as JWTs cannot be split into apparently harmless fragments.
        if (
            classify_memory_sensitivity(user_message) == "credential"
            or _has_ambiguous_dotted_token_boundary(user_message)
        ):
            return []
        raw = deterministic_candidates(user_message) if use_mock else await request_candidates(
            model or create_chat_model(0.0), user_message, assistant_message,
        )
        return validate_and_filter_candidates(raw, user_message)
    except Exception:
        return []
