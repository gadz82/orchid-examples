"""Secret scanning lane — gitleaks-style regex + entropy detection.

One implementation applied at THREE points (SPEC §7):
  1. Indexing time — every chunk scanned before embedding.
  2. Runtime capture writes — GitLab/Datadog results scanned before inject_to_rag.
  3. Output redaction — last-resort net on live tool passthrough.

Ships as a standalone module so Phases 5 and 8 can reuse it.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SecretFinding:
    rule: str
    match: str  # redacted in logs
    path: str = ""


@dataclass
class SecretScanResult:
    dirty: bool = False
    cleaned_text: str = ""
    findings: list[SecretFinding] = field(default_factory=list)
    redacted_ratio: float = 0.0  # fraction of text redacted


# ── Gitleaks-style regex rules ────────────────────────────────

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws-access-key", re.compile(r"(?:A3T[A-Z0-9]|AKIA|ASIA|AROA|AIDA)[A-Z0-9]{16}", re.IGNORECASE)),
    ("aws-secret-key", re.compile(r"(?i)(?:secret|token|password).*?['\"]?([A-Za-z0-9/+=]{40})['\"]?")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}")),
    ("gitlab-token", re.compile(r"glpat-[A-Za-z0-9\-_]{20,64}")),
    ("generic-api-key", re.compile(r"(?i)(?:api[_-]?key|apikey|api[_-]?secret)['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9+/=_-]{20,})['\"]?")),
    ("bearer-token", re.compile(r"(?i)bearer\s+([A-Za-z0-9+/=_-]{20,})")),
    ("private-key", re.compile(r"-----BEGIN\s+(?:RSA|EC|DSA|OPENSSH|PGP)\s+PRIVATE\s+KEY-----")),
    ("smtp-password", re.compile(r"(?i)SMTP_(?:PASS|PWD|PASSWORD)\s*[:=]\s*['\"]?(\S+)['\"]?")),
    ("dsn-credentials", re.compile(r"(?i)(?:mysql|postgres(?:ql)?|mongodb)://[^:]+:([^@]+)@")),
    ("slack-token", re.compile(r"xox[bpsar]-[A-Za-z0-9\-]+")),
    ("jwt-token", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("generic-password", re.compile(r"(?i)(?:password|passwd|pwd)['\"]?\s*[:=]\s*['\"]?(\S{4,})['\"]?")),
]


def _entropy(data: str) -> float:
    """Shannon entropy of a string.  Higher = more random."""
    if not data:
        return 0.0
    n = len(data)
    counts = Counter(data)
    probs = (c / n for c in counts.values())
    return -sum(p * math.log2(p) for p in probs if p > 0)


def _high_entropy_token(token: str, threshold: float = 4.5) -> bool:
    """Return True if token looks like a high-entropy key/token."""
    if len(token) < 16:
        return False
    if len(token) > 256:
        return False
    return _entropy(token) > threshold


class SecretScanner:
    """Regex + entropy lane for credential detection."""

    def __init__(self, entropy_threshold: float = 4.5) -> None:
        self._entropy_threshold = entropy_threshold

    def scan(self, text: str, path: str = "") -> SecretScanResult:
        """Scan text for secrets. Returns cleaned text + findings."""
        findings: list[SecretFinding] = []
        cleaned = text

        for rule_name, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(cleaned):
                secret_value = m.group(0)
                findings.append(SecretFinding(rule=rule_name, match="[REDACTED]", path=path))
                cleaned = cleaned.replace(secret_value, "[REDACTED]")
                logger.debug("Secret found: rule=%s path=%s", rule_name, path)

        # Entropy pass: find remaining high-entropy strings
        token_re = re.compile(r"[A-Za-z0-9+/=_-]{20,80}")
        for m in token_re.finditer(cleaned):
            token = m.group(0)
            # Avoid double-redacting already-redacted content
            if _high_entropy_token(token, self._entropy_threshold) and "[REDACTED]" not in token:
                findings.append(SecretFinding(rule="entropy", match="[REDACTED]", path=path))
                cleaned = cleaned.replace(token, "[REDACTED]")
                logger.debug("High-entropy token: path=%s len=%d", path, len(token))

        dirty = len(findings) > 0
        original_len = max(len(text), 1)
        # Approximate redacted character count by removing the redaction markers
        # and comparing with the original length.
        redacted_chars = original_len - len(cleaned.replace("[REDACTED]", ""))
        ratio = min(redacted_chars / original_len, 1.0) if findings else 0.0

        return SecretScanResult(
            dirty=dirty,
            cleaned_text=cleaned,
            findings=findings,
            redacted_ratio=ratio,
        )

    def should_skip_chunk(self, result: SecretScanResult) -> bool:
        """Skip chunk if >50% was redacted."""
        return result.redacted_ratio > 0.5
