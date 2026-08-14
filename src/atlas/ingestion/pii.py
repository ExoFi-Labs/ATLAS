from __future__ import annotations

import re
from typing import Protocol


class PIIScrubber(Protocol):
    def scrub(self, text: str) -> tuple[str, dict[str, int]]: ...


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4})")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
EMPLOYEE_ID_RE = re.compile(r"\b(?:EMP|EID)[- ]?\d{4,8}\b", re.IGNORECASE)


class RegexPIIScrubber:
    """Default on-prem scrubber. Swap for Presidio later without changing the pipeline."""

    def scrub(self, text: str) -> tuple[str, dict[str, int]]:
        hits: dict[str, int] = {}

        def _sub(pattern: re.Pattern[str], token: str, source: str) -> str:
            matches = pattern.findall(source)
            if matches:
                hits[token] = hits.get(token, 0) + len(matches)
            return pattern.sub(token, source)

        cleaned = text
        cleaned = _sub(EMAIL_RE, "[EMAIL]", cleaned)
        cleaned = _sub(PHONE_RE, "[PHONE]", cleaned)
        cleaned = _sub(SSN_RE, "[SSN]", cleaned)
        cleaned = _sub(EMPLOYEE_ID_RE, "[EMPLOYEE_ID]", cleaned)
        cleaned = _sub(CARD_RE, "[CARD]", cleaned)
        return cleaned, hits
