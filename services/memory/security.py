"""Privacy classification and normalization for long-term memory text."""

import ipaddress
import math
import re
from collections import Counter
from typing import Literal
from urllib.parse import unquote, unquote_plus, urlsplit


Sensitivity = Literal["normal", "personal_sensitive", "credential"]

_MAX_MEMORY_CHARACTERS = 500
_EXPLICIT_MEMORY_RE = re.compile(
    r"(?:请|麻烦|帮我)?(?:记住|记下|记一下|保存|存下|留存)"
    r"|(?:please\s+)?remember\b|save\s+(?:this|that|it)\b",
    re.IGNORECASE,
)
_NEGATED_MEMORY_RE = re.compile(
    r"(?:请\s*)?(?:不要|别|勿|无需|不必)\s*(?:再\s*)?"
    r"(?:记住|记下|记录|保存|存下|留存)"
    r"|\b(?:(?:please\s+)?do\s+not|don['’]?t|dont|never)\s+"
    r"(?:remember|save|store|retain|memorize)\b",
    re.IGNORECASE,
)
_CREDENTIAL_LABEL_PATTERNS = (
    re.compile(r"(?:验证码|校验码|短信码|动态码|一次性密码|一次性口令)", re.IGNORECASE),
    re.compile(r"\botp\b|one[-\s]?time\s+(?:password|code)\b", re.IGNORECASE),
    re.compile(r"密码(?!学)|口令", re.IGNORECASE),
    re.compile(r"\b(?:password|passwd|passcode)\b", re.IGNORECASE),
    re.compile(r"\b(?:access|refresh|auth)[_\s-]?token\b", re.IGNORECASE),
    re.compile(r"\btoken\b", re.IGNORECASE),
    re.compile(r"\bapi[_\s-]?key\b", re.IGNORECASE),
    re.compile(r"\bclient[_\s-]?secret\b", re.IGNORECASE),
    re.compile(r"\b(?:secret|private)[_\s-]?key\b", re.IGNORECASE),
    re.compile(r"\baws[_\s-]?(?:access[_\s-]?key[_\s-]?id|secret[_\s-]?access[_\s-]?key)\b", re.IGNORECASE),
    re.compile(r"(?:客户端密钥|访问密钥|秘密密钥|私钥|密钥)", re.IGNORECASE),
)
_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{6,}", re.IGNORECASE),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b", re.IGNORECASE),
    re.compile(r"\bxox[a-z]-[A-Za-z0-9-]{10,}\b", re.IGNORECASE),
    re.compile(r"\bglpat-[A-Za-z0-9_-]{10,}\b", re.IGNORECASE),
    re.compile(r"\bnpm_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"\bpypi-[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"\b(?:shpat|shpca|shppa|shpss)_[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{12,}\b", re.IGNORECASE),
    re.compile(r"\b(?:dop_v1_|dapi)[A-Za-z0-9]{20,}\b", re.IGNORECASE),
    re.compile(r"\bya29\.[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bSG\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bmfa\.[A-Za-z0-9_-]{20,}\b", re.IGNORECASE),
    re.compile(r"\bSK[0-9a-f]{32}\b", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    re.compile(r"-----BEGIN\s+(?:(?:RSA|EC|DSA|OPENSSH)\s+)?PRIVATE KEY-----", re.IGNORECASE),
)
_CREDENTIAL_PATTERNS = (*_CREDENTIAL_LABEL_PATTERNS, *_CREDENTIAL_VALUE_PATTERNS)
_URL_LABELED_CREDENTIAL_RE = re.compile(
    r"(?<![\w-])(?:"
    r"验证码|校验码|短信码|动态码|一次性密码|一次性口令|密码|口令|"
    r"otp|one[-_\s]?time[-_\s]?(?:password|code)|"
    r"password|passwd|passcode|(?:access|refresh|auth)[-_\s]?token|token|"
    r"api[-_\s]?key|client[-_\s]?secret|(?:secret|private)[-_\s]?key|"
    r"aws[-_\s]?(?:access[-_\s]?key[-_\s]?id|secret[-_\s]?access[-_\s]?key)|"
    r"客户端密钥|访问密钥|秘密密钥|私钥|密钥"
    r")(?![\w-])\s*[:=]\s*[^\s/?#&;]+",
    re.IGNORECASE,
)
_COMPACT_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z0-9_+=/-]{32,})(?![A-Za-z0-9])"
)
_ALNUM_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z0-9]{32,128})(?![A-Za-z0-9])"
)
_LONG_HEX_TOKEN_RE = re.compile(
    r"(?<![A-Fa-f0-9])([A-Fa-f0-9]{48,128})(?![A-Fa-f0-9])"
)
_URL_RE = re.compile(
    r"https?://(?:\[[^\]\s<>(){}]+\](?::\d+)?[^\s<>()\[\]{}]*|[^\s<>()\[\]{}]+)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_HOST_LABEL_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_PERSONAL_SENSITIVE_PATTERNS = (
    # Contact details.
    re.compile(r"(?:手机(?:号|号码)?|电话号码?|联系电话|邮箱|电子邮件|微信(?:号)?|QQ(?:号)?)", re.IGNORECASE),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    # Identity and exact location identifiers.
    re.compile(r"(?:身份证(?:号|号码)?|护照(?:号|号码)?|社会保障号|社保号|姓名|名字|出生日期|生日|住址|家庭地址)", re.IGNORECASE),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    # Financial information.
    re.compile(r"(?:银行卡(?:号|号码)?|银行账户|账户余额|信用卡|借记卡|支付账号|收入|工资|薪资|负债)", re.IGNORECASE),
    # Health information.
    re.compile(r"(?:健康状况|病史|病历|医疗|诊断|患有|确诊|疾病|症状|过敏|用药|服药|处方|残疾|血型|哮喘|抑郁|焦虑症)", re.IGNORECASE),
)


def normalize_memory_text(text: str) -> str:
    """Collapse whitespace and enforce the storage boundary."""
    return " ".join(str(text or "").split())[:_MAX_MEMORY_CHARACTERS].strip()


def has_explicit_memory_intent(text: str) -> bool:
    """Return whether the user explicitly asked for durable remembering."""
    source = str(text or "")
    if has_negated_memory_intent(source):
        return False
    return bool(_EXPLICIT_MEMORY_RE.search(source))


def has_negated_memory_intent(text: str) -> bool:
    """Return whether the user explicitly refused durable remembering."""
    return bool(_NEGATED_MEMORY_RE.search(str(text or "")))


def _token_entropy(token: str) -> float:
    counts = Counter(token)
    return -sum(
        (count / len(token)) * math.log2(count / len(token))
        for count in counts.values()
    )


def _has_mixed_high_entropy(token: str, *, require_marker: bool) -> bool:
    if _UUID_RE.fullmatch(token):
        return False
    if require_marker and not any(character in "_+=" for character in token):
        return False
    character_classes = sum((
        any(character.islower() for character in token),
        any(character.isupper() for character in token),
        any(character.isdigit() for character in token),
        any(character in "_+=/-" for character in token),
    ))
    return character_classes >= 3 and _token_entropy(token) >= 4.0


def _contains_token_like_credential(text: str) -> bool:
    """Check one unprotected token-bearing value without logging its content."""
    if any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS):
        return True
    for match in _LONG_HEX_TOKEN_RE.finditer(text):
        if not _UUID_RE.fullmatch(match.group(1)):
            return True
    for match in _COMPACT_TOKEN_RE.finditer(text):
        if _has_mixed_high_entropy(match.group(1), require_marker=True):
            return True
    for match in _ALNUM_TOKEN_RE.finditer(text):
        if _has_mixed_high_entropy(match.group(1), require_marker=False):
            return True
    return False


def _decoded_variants(value: str) -> tuple[str, ...]:
    decoded = unquote(value)
    return (value, decoded) if decoded != value else (value,)


def _contains_url_component_credential(value: str, *, decode: bool = True) -> bool:
    """Inspect one URL value without treating readable label words as secrets."""
    for candidate in _decoded_variants(value) if decode else (value,):
        if (
            any(pattern.search(candidate) for pattern in _CREDENTIAL_VALUE_PATTERNS)
            or _URL_LABELED_CREDENTIAL_RE.search(candidate)
        ):
            return True
        for match in _LONG_HEX_TOKEN_RE.finditer(candidate):
            if not _UUID_RE.fullmatch(match.group(1)):
                return True
        for match in _COMPACT_TOKEN_RE.finditer(candidate):
            if _has_mixed_high_entropy(match.group(1), require_marker=True):
                return True
        for match in _ALNUM_TOKEN_RE.finditer(candidate):
            if _has_mixed_high_entropy(match.group(1), require_marker=False):
                return True
    return False


def _query_contains_credential(query: str) -> bool:
    """Decode the complete query once before interpreting its delimiters."""
    if re.search(r"%(?![0-9A-Fa-f]{2})", query):
        return True
    # Strict UTF-8 errors are caught by the enclosing URL fail-closed boundary.
    # Inspect raw text too: a literal '+' may be part of a compact secret.
    decoded = unquote_plus(query, errors="strict")
    for candidate in (query, decoded) if decoded != query else (query,):
        if _contains_url_component_credential(candidate, decode=False):
            return True
        for field in candidate.split("&"):
            key, separator, value = field.partition("=")
            if separator and value and _URL_LABELED_CREDENTIAL_RE.fullmatch(f"{key.strip()}=x"):
                return True
            if any(
                _contains_url_component_credential(part, decode=False)
                for part in (key, value)
            ):
                return True
    return False


def _is_valid_url_hostname(hostname: str) -> bool:
    """Accept IP literals and IDNA host labels, excluding unsafe authority text."""
    if ":" in hostname:
        address = hostname.split("%", 1)[0]
        return ipaddress.ip_address(address).version == 6

    candidate = hostname.rstrip(".")
    if not candidate:
        return False
    if re.fullmatch(r"\d+(?:\.\d+){3}", candidate):
        return ipaddress.ip_address(candidate).version == 4
    ascii_hostname = candidate.encode("idna").decode("ascii")
    return len(ascii_hostname) <= 253 and all(
        _HOST_LABEL_RE.fullmatch(label) and len(label) <= 63
        for label in ascii_hostname.split(".")
    )


def _url_contains_credential(url: str) -> bool:
    """Fail closed on malformed URLs and inspect security-relevant components."""
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        # Accessing port performs its range and integer validation.
        _ = parts.port
        if not parts.netloc or not hostname or not _is_valid_url_hostname(hostname):
            return True
        if parts.password not in (None, ""):
            return True
        if parts.username and any(
            _contains_token_like_credential(candidate)
            for candidate in _decoded_variants(parts.username)
        ):
            return True

        for segment in parts.path.split("/"):
            if segment and _contains_url_component_credential(segment):
                return True

        if parts.query and _query_contains_credential(parts.query):
            return True

        return bool(
            parts.fragment
            and _contains_url_component_credential(parts.fragment)
        )
    except Exception:
        # URL parsing errors may include the original netloc in their message.
        # Classification deliberately records or exposes none of that detail.
        return True


def _url_spans_and_credential_status(
    text: str,
) -> tuple[tuple[tuple[int, int], ...], bool]:
    spans: list[tuple[int, int]] = []
    for match in _URL_RE.finditer(text):
        spans.append(match.span())
        if _url_contains_credential(match.group()):
            return tuple(spans), True
    return tuple(spans), False


def _without_spans(text: str, spans: tuple[tuple[int, int], ...]) -> str:
    if not spans:
        return text
    characters = list(text)
    for start, end in spans:
        characters[start:end] = " " * (end - start)
    return "".join(characters)


def _looks_like_high_entropy_credential(text: str) -> bool:
    """Inspect compact secrets while retaining the existing email exemption."""
    protected_spans = [match.span() for match in _EMAIL_RE.finditer(text)]

    def is_protected(start: int, end: int) -> bool:
        return any(
            start < protected_end and end > protected_start
            for protected_start, protected_end in protected_spans
        )

    for match in _LONG_HEX_TOKEN_RE.finditer(text):
        if not is_protected(*match.span(1)) and not _UUID_RE.fullmatch(match.group(1)):
            return True
    for match in _COMPACT_TOKEN_RE.finditer(text):
        if not is_protected(*match.span(1)) and _has_mixed_high_entropy(
            match.group(1), require_marker=True,
        ):
            return True
    for match in _ALNUM_TOKEN_RE.finditer(text):
        if not is_protected(*match.span(1)) and _has_mixed_high_entropy(
            match.group(1), require_marker=False,
        ):
            return True
    return False


def classify_memory_sensitivity(text: str) -> Sensitivity:
    """Classify credentials before other personal-sensitive forms."""
    # Scan the full source; the 500-character limit applies only to stored text.
    normalized = " ".join(str(text or "").split())
    url_spans, url_has_credential = _url_spans_and_credential_status(normalized)
    non_url_text = _without_spans(normalized, url_spans)
    if (
        url_has_credential
        or any(pattern.search(non_url_text) for pattern in _CREDENTIAL_PATTERNS)
        or _looks_like_high_entropy_credential(non_url_text)
    ):
        return "credential"
    if any(pattern.search(normalized) for pattern in _PERSONAL_SENSITIVE_PATTERNS):
        return "personal_sensitive"
    return "normal"


def sanitize_memory_text(text: str, *, explicitly_requested: bool = False) -> str:
    """Normalize safe text, returning an empty string when policy rejects it."""
    normalized = normalize_memory_text(text)
    if not normalized:
        return ""
    sensitivity = classify_memory_sensitivity(normalized)
    if sensitivity == "credential":
        return ""
    if sensitivity == "personal_sensitive" and not explicitly_requested:
        return ""
    return normalized
