from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ParsedEmail:
    message_id: str
    in_reply_to: str | None
    references: list[str]
    date: datetime | None
    sender: str
    to: list[str]
    cc: list[str]
    subject: str
    body_raw: str
    source_path: str = ""


@dataclass
class CleanedEmail:
    message_id: str
    thread_id: str
    in_reply_to: str | None
    date: datetime | None
    sender: str
    to: list[str]
    cc: list[str]
    subject: str
    body: str
    body_hash: str
    position_in_thread: int = 0
    source_path: str = ""
    pii_hits: dict[str, int] = field(default_factory=dict)


@dataclass
class EmailChunk:
    chunk_id: str
    text: str
    message_id: str
    thread_id: str
    part_index: int
    subject: str
    sender: str
    date_iso: str
    department: str
    allowed_roles: list[str]
    metadata: dict
