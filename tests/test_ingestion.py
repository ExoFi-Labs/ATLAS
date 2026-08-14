from pathlib import Path

from atlas.ingestion.chunk import chunk_messages
from atlas.ingestion.clean import clean_messages, strip_quoted_reply
from atlas.ingestion.parse import parse_path
from atlas.ingestion.pii import RegexPIIScrubber

FIXTURES = Path(__file__).resolve().parents[1] / "examples" / "emails"


def test_parse_sample_corpus():
    messages = parse_path(FIXTURES)
    assert len(messages) == 6
    subjects = {item.subject for item in messages}
    assert any("PTO policy" in subject for subject in subjects)
    html_message = next(item for item in messages if "expense" in item.source_path)
    assert "Coupa" in html_message.body_raw
    assert "<li>" not in html_message.body_raw


def test_reply_chain_keeps_new_content_only():
    messages = parse_path(FIXTURES)
    reply = next(item for item in messages if item.message_id == "<pto-policy-reply@company.internal>")
    body = strip_quoted_reply(reply.body_raw)
    assert "December holiday shutdown" in body
    assert "1.67 days of PTO" not in body


def test_thread_reconstruction_and_pii():
    messages = parse_path(FIXTURES)
    cleaned = clean_messages(messages)
    pto_thread = [item for item in cleaned if item.thread_id == "<pto-policy-root@company.internal>"]
    assert len(pto_thread) == 3
    assert {item.position_in_thread for item in pto_thread} == {0, 1, 2}

    expense = next(item for item in cleaned if "Expense reimbursement" in item.subject)
    assert "[EMAIL]" in expense.body
    assert "[EMPLOYEE_ID]" in expense.body
    assert "EMP-20481" not in expense.body
    jane = next(item for item in cleaned if item.message_id == "<pto-policy-root@company.internal>")
    assert "PTO policy is updated" in jane.body
    assert "415-555-0198" not in jane.body
    assert "jane.okoye@company.internal" not in jane.body


def test_message_level_chunks_include_metadata():
    messages = parse_path(FIXTURES)
    cleaned = clean_messages(messages)
    chunks = chunk_messages(cleaned, department="hr", allowed_roles=["all-staff", "hr"])
    assert chunks
    sample = chunks[0]
    assert sample.text.startswith("Subject:")
    assert sample.metadata["allowed_roles"] == ["all-staff", "hr"]
    assert sample.metadata["department"] == "hr"
    ids = {chunk.chunk_id for chunk in chunks}
    assert len(ids) == len(chunks)


def test_regex_pii_scrubber():
    text = "Call 415-555-0198 or email ada@company.internal. ID EMP-20481 SSN 123-45-6789."
    cleaned, hits = RegexPIIScrubber().scrub(text)
    assert "[PHONE]" in cleaned
    assert "[EMAIL]" in cleaned
    assert "[EMPLOYEE_ID]" in cleaned
    assert "[SSN]" in cleaned
    assert hits["[EMAIL]"] == 1
