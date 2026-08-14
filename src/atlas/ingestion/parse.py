from __future__ import annotations

import mailbox
from email import policy
from email.parser import BytesParser
from datetime import datetime
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

from atlas.ingestion.attachments import extract_attachment
from atlas.ingestion.models import ParsedAttachment, ParsedEmail


class _HTMLToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip = True
        if tag in {"br", "p", "div", "tr", "li", "h1", "h2", "h3"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False
        if tag in {"p", "div", "tr", "li"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def html_to_text(html: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return html
    return parser.text()


def iter_email_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for pattern in ("*.eml", "*.mbox"):
        files.extend(sorted(path.rglob(pattern)))
    return files


def parse_path(path: Path) -> list[ParsedEmail]:
    messages: list[ParsedEmail] = []
    for file_path in iter_email_files(path):
        suffix = file_path.suffix.lower()
        if suffix == ".mbox":
            messages.extend(_parse_mbox(file_path))
        else:
            messages.append(_parse_eml(file_path))
    return messages


def parse_bytes(raw: bytes, source_path: str = "") -> ParsedEmail:
    message = BytesParser(policy=policy.default).parsebytes(raw)
    return _from_email_message(message, source_path)


def _parse_eml(path: Path) -> ParsedEmail:
    raw = path.read_bytes()
    return parse_bytes(raw, source_path=str(path))


def _parse_mbox(path: Path) -> list[ParsedEmail]:
    box = mailbox.mbox(path)
    parsed: list[ParsedEmail] = []
    try:
        for index, message in enumerate(box):
            parsed.append(parse_bytes(message.as_bytes(), f"{path}#{index}"))
    finally:
        box.close()
    return parsed


def _from_email_message(message, source_path: str) -> ParsedEmail:
    message_id = (message.get("Message-ID") or "").strip() or f"generated-{abs(hash(source_path))}"
    in_reply_to = (message.get("In-Reply-To") or "").strip() or None
    references = [token for token in (message.get("References") or "").split() if token]
    subject = str(message.get("Subject") or "(no subject)").strip()
    sender = _format_addresses(message.get("From"))[0] if message.get("From") else ""
    to = _format_addresses(message.get("To"))
    cc = _format_addresses(message.get("Cc"))
    date = _parse_date(message.get("Date"))
    body, attachments = _extract_body_and_attachments(message)
    return ParsedEmail(
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        date=date,
        sender=sender,
        to=to,
        cc=cc,
        subject=subject,
        body_raw=body,
        source_path=source_path,
        attachments=attachments,
    )


def _format_addresses(value) -> list[str]:
    if not value:
        return []
    return [f"{name} <{addr}>".strip() if name else addr for name, addr in getaddresses([str(value)])]


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(str(value))
    except (TypeError, ValueError, IndexError):
        return None


def _extract_body_and_attachments(message) -> tuple[str, list[ParsedAttachment]]:
    if not message.is_multipart():
        payload = message.get_content()
        if message.get_content_type() == "text/html" and isinstance(payload, str):
            return html_to_text(payload).strip(), []
        return str(payload or "").strip(), []

    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[ParsedAttachment] = []
    for part in message.walk():
        content_type = part.get_content_type()
        if content_type.startswith("multipart/"):
            continue
        filename = part.get_filename() or ""
        disposition = str(part.get("Content-Disposition") or "").lower()
        is_attachment = bool(filename) or "attachment" in disposition or _looks_like_file(content_type)

        if is_attachment:
            raw = part.get_payload(decode=True)
            if not isinstance(raw, (bytes, bytearray)):
                raw = b""
            attachments.append(extract_attachment(filename or "attachment", content_type, bytes(raw)))
            continue

        try:
            payload = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True)
            if isinstance(payload, bytes):
                payload = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if not isinstance(payload, str):
            continue
        if content_type == "text/plain":
            text_parts.append(payload)
        elif content_type == "text/html":
            html_parts.append(html_to_text(payload))

    body = "\n\n".join(text_parts).strip() if text_parts else "\n\n".join(html_parts).strip()
    return body, attachments


def _looks_like_file(content_type: str) -> bool:
    main = (content_type or "").split("/", 1)[0]
    return main in {"application", "image", "audio", "video"}
