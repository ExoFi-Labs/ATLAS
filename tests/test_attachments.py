from email.message import EmailMessage

from atlas.ingestion.attachments import extract_attachment
from atlas.ingestion.chunk import chunk_messages
from atlas.ingestion.clean import clean_messages
from atlas.ingestion.parse import parse_bytes


def _pdf_with_text(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii"))
    return bytes(out)


def _email_with_pdf() -> bytes:
    message = EmailMessage()
    message["From"] = "ap@company.internal"
    message["To"] = "finance@company.internal"
    message["Subject"] = "PO-4412 attached"
    message["Message-ID"] = "<po-4412@company.internal>"
    message["Date"] = "Thu, 15 Aug 2026 10:00:00 +1000"
    message.set_content("Please process the attached purchase order.")
    message.add_attachment(
        _pdf_with_text("Purchase Order PO-4412 Amount due 1850.00 net 30"),
        maintype="application",
        subtype="pdf",
        filename="PO-4412.pdf",
    )
    return message.as_bytes()


def test_pdf_attachment_is_extracted_and_chunked():
    parsed = parse_bytes(_email_with_pdf(), source_path="memory:po.eml")
    assert parsed.body_raw.startswith("Please process")
    assert len(parsed.attachments) == 1
    attachment = parsed.attachments[0]
    assert attachment.filename == "PO-4412.pdf"
    assert "PO-4412" in attachment.text or "PO-4412" in (attachment.skipped_reason or "")

    cleaned = clean_messages([parsed])
    chunks = chunk_messages(cleaned, department="finance", allowed_roles=["finance"])
    kinds = {chunk.metadata.get("kind") for chunk in chunks}
    assert "email" in kinds
    if attachment.text:
        assert "attachment" in kinds
        assert any("PO-4412.pdf" in chunk.text for chunk in chunks)


def test_image_attachment_is_skipped_without_ocr():
    result = extract_attachment("scan.png", "image/png", b"\x89PNG\r\n")
    assert result.text == ""
    assert "OCR" in result.skipped_reason
