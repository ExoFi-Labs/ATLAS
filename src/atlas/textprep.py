"""Tiny, zero-model text cleanup for display and TTS (microseconds, not a second LLM)."""

from __future__ import annotations

import re

_CITATION_RE = re.compile(r"\[[0-9,\s]+\]")
_SOP_RE = re.compile(r"\bSOP-([A-Za-z]+)-(\d+)\b")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC_RE = re.compile(
    r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)|(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)"
)
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_FENCE_RE = re.compile(r"```[\s\S]*?```")
_TICK_RE = re.compile(r"`([^`]+)`")
_MARKUP_RE = re.compile(r"[*_~`#]+")
_ATP_RE = re.compile(r"\bATP\b")


def _unwrap_markup(text: str) -> str:
    out = (text or "").replace("\r\n", "\n")
    out = _FENCE_RE.sub(" ", out)
    out = _TICK_RE.sub(r"\1", out)
    out = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2) or "", out)
    out = _ITALIC_RE.sub(lambda m: m.group(1) or m.group(2) or "", out)
    out = _HEADING_RE.sub("", out)
    out = _MARKUP_RE.sub("", out)
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()


def for_display(text: str) -> str:
    """Drop markdown markers so chat does not show raw asterisks."""
    return _unwrap_markup(text)


def for_speech(text: str) -> str:
    """Same unwrap, plus speakable SOP / ATP and no citation brackets."""
    out = _unwrap_markup(text)
    out = _CITATION_RE.sub("", out)
    out = _SOP_RE.sub(r"SOP \1 \2", out)
    out = _ATP_RE.sub("available to promise", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip()
