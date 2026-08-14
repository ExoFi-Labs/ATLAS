from __future__ import annotations

import uuid
from datetime import timezone

from atlas.ingestion.models import CleanedEmail, EmailChunk

CHARS_PER_TOKEN = 4


def chunk_messages(
    messages: list[CleanedEmail],
    *,
    department: str,
    allowed_roles: list[str],
    max_tokens: int = 1200,
) -> list[EmailChunk]:
    chunks: list[EmailChunk] = []
    seen_hashes: set[str] = set()
    max_chars = max_tokens * CHARS_PER_TOKEN

    for message in messages:
        if message.body:
            dedupe_key = f"{message.thread_id}:{message.body_hash}"
            if dedupe_key not in seen_hashes:
                seen_hashes.add(dedupe_key)
                parts = _split_body(message.body, max_chars)
                for part_index, part in enumerate(parts):
                    chunks.append(
                        _make_chunk(
                            message,
                            part,
                            part_index=part_index,
                            department=department,
                            allowed_roles=allowed_roles,
                            kind="email",
                            filename="",
                        )
                    )

        for attachment in message.attachments:
            if not attachment.text:
                continue
            attach_parts = _split_body(attachment.text, max_chars)
            for part_index, part in enumerate(attach_parts):
                labeled = (
                    f"Attachment: {attachment.filename} ({attachment.content_type})\n\n{part}"
                )
                chunks.append(
                    _make_chunk(
                        message,
                        labeled,
                        part_index=1000 + part_index,
                        department=department,
                        allowed_roles=allowed_roles,
                        kind="attachment",
                        filename=attachment.filename,
                    )
                )
    return chunks


def _make_chunk(
    message: CleanedEmail,
    body: str,
    *,
    part_index: int,
    department: str,
    allowed_roles: list[str],
    kind: str,
    filename: str,
) -> EmailChunk:
    text = _render_chunk(message, body)
    chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{message.message_id}:{kind}:{filename}:{part_index}"))
    return EmailChunk(
        chunk_id=chunk_id,
        text=text,
        message_id=message.message_id,
        thread_id=message.thread_id,
        part_index=part_index,
        subject=message.subject,
        sender=message.sender,
        date_iso=_date_iso(message),
        department=department,
        allowed_roles=allowed_roles,
        metadata={
            "message_id": message.message_id,
            "thread_id": message.thread_id,
            "part_index": part_index,
            "subject": message.subject,
            "from": message.sender,
            "to": message.to,
            "date": _date_iso(message),
            "department": department,
            "allowed_roles": allowed_roles,
            "position_in_thread": message.position_in_thread,
            "source_path": message.source_path,
            "kind": kind,
            "filename": filename,
        },
    )


def _render_chunk(message: CleanedEmail, body: str) -> str:
    recipients = ", ".join(message.to[:4])
    return (
        f"Subject: {message.subject}\n"
        f"Thread: {message.thread_id}\n"
        f"Date: {_date_iso(message)} | From: {message.sender} | To: {recipients}\n\n"
        f"{body}"
    )


def _split_body(body: str, max_chars: int) -> list[str]:
    if len(body) <= max_chars:
        return [body]

    paragraphs = [block.strip() for block in body.split("\n\n") if block.strip()]
    parts: list[str] = []
    current = ""
    for paragraph in paragraphs or [body]:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            parts.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            for start in range(0, len(paragraph), max_chars):
                parts.append(paragraph[start : start + max_chars])
            current = ""
    if current:
        parts.append(current)
    return parts or [body[:max_chars]]


def _date_iso(message: CleanedEmail) -> str:
    if not message.date:
        return ""
    value = message.date
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
