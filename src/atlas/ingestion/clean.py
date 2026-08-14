from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from atlas.ingestion.models import CleanedEmail, ParsedAttachment, ParsedEmail
from atlas.ingestion.pii import PIIScrubber, RegexPIIScrubber

QUOTE_HEADER_RE = re.compile(
    r"^(On\s.+wrote:|From:\s.+|Sent:\s.+|To:\s.+|Subject:\s.+|-----Original Message-----)\s*$",
    re.IGNORECASE,
)
SIGNATURE_RE = re.compile(
    r"^(--|__|Best regards,?|Kind regards,?|Regards,?|Thanks,?|Thank you,?|Sent from my)\b",
    re.IGNORECASE,
)
CONFIDENTIAL_RE = re.compile(r"(confidential|privileged|intended only for)", re.IGNORECASE)
REPLY_SUBJECT_RE = re.compile(r"^(re|fw|fwd):\s*", re.IGNORECASE)


def normalize_subject(subject: str) -> str:
    cleaned = subject.strip()
    while True:
        updated = REPLY_SUBJECT_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            return cleaned.strip() or "(no subject)"
        cleaned = updated


def strip_quoted_reply(body: str) -> str:
    lines = body.replace("\r\n", "\n").split("\n")
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            break
        if QUOTE_HEADER_RE.match(stripped):
            break
        kept.append(line)
    return "\n".join(kept).strip()


def strip_signature(body: str) -> str:
    lines = body.split("\n")
    cut_at = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "--" or stripped.startswith("-- "):
            cut_at = index
            break
        if index > 1 and SIGNATURE_RE.match(stripped) and index >= len(lines) - 8:
            cut_at = index
            break
        if CONFIDENTIAL_RE.search(stripped) and index >= len(lines) - 6:
            cut_at = index
            break
    return "\n".join(lines[:cut_at]).strip()


def normalize_whitespace(body: str) -> str:
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def thread_id_for(message: ParsedEmail, by_id: dict[str, ParsedEmail]) -> str:
    if message.references:
        return message.references[0]
    if message.in_reply_to:
        parent = by_id.get(message.in_reply_to)
        if parent:
            return thread_id_for(parent, by_id)
        return message.in_reply_to
    return message.message_id


def clean_messages(
    messages: list[ParsedEmail],
    *,
    scrubber: PIIScrubber | None = None,
) -> list[CleanedEmail]:
    scrubber = scrubber or RegexPIIScrubber()
    by_id = {message.message_id: message for message in messages}
    grouped: dict[str, list[ParsedEmail]] = defaultdict(list)

    for message in messages:
        grouped[thread_id_for(message, by_id)].append(message)

    cleaned: list[CleanedEmail] = []
    for thread_id, thread_messages in grouped.items():
        ordered = sorted(thread_messages, key=lambda item: (item.date is None, item.date, item.message_id))
        for position, message in enumerate(ordered):
            body = strip_quoted_reply(message.body_raw)
            body = strip_signature(body)
            body = normalize_whitespace(body)
            body, pii_hits = scrubber.scrub(body)
            body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
            cleaned_attachments: list[ParsedAttachment] = []
            for attachment in message.attachments:
                if not attachment.text:
                    cleaned_attachments.append(attachment)
                    continue
                text, extra_hits = scrubber.scrub(attachment.text)
                for token, count in extra_hits.items():
                    pii_hits[token] = pii_hits.get(token, 0) + count
                cleaned_attachments.append(
                    ParsedAttachment(
                        filename=attachment.filename,
                        content_type=attachment.content_type,
                        text=text,
                        skipped_reason=attachment.skipped_reason,
                    )
                )
            cleaned.append(
                CleanedEmail(
                    message_id=message.message_id,
                    thread_id=thread_id,
                    in_reply_to=message.in_reply_to,
                    date=message.date,
                    sender=message.sender,
                    to=message.to,
                    cc=message.cc,
                    subject=normalize_subject(message.subject),
                    body=body,
                    body_hash=body_hash,
                    position_in_thread=position,
                    source_path=message.source_path,
                    pii_hits=pii_hits,
                    attachments=cleaned_attachments,
                )
            )
    return cleaned
