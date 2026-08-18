from atlas.config import OrgSettings
from atlas.providers.base import RetrievedChunk
from atlas.rag.pipeline import (
    compose_search_query,
    extract_identifiers,
    retrieval_queries,
    select_chunks,
    system_prompt_for,
)


def _chunk(text: str, score: float, message_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=message_id,
        text=text,
        score=score,
        metadata={"message_id": message_id, "subject": "test"},
    )


def test_retrieval_queries_add_wholesale_hints():
    queries = retrieval_queries("Where is the delivery for order 451234567?")
    assert queries[0].startswith("Where is")
    assert any("ETA" in item or "consignment" in item for item in queries)


def test_extract_identifiers():
    ids = extract_identifiers("Please check RA-24100 against order 451112223 and INV-910001")
    assert "RA-24100" in ids
    assert "451112223" in ids
    assert "INV-910001" in ids


def test_system_prompt_switches_reply_length():
    org = OrgSettings()
    short = system_prompt_for(org, "short")
    regular = system_prompt_for(org, "regular")
    assert "SHORT" in short
    assert "few short sentences" in short
    assert "Do not use bullets" in short
    assert "REGULAR" in regular
    assert "few short sentences" not in regular


def test_system_prompt_switches_staff_role():
    org = OrgSettings()
    cs = system_prompt_for(org, staff_role="customer_service")
    sales = system_prompt_for(org, staff_role="sales")
    unknown = system_prompt_for(org, staff_role="warehouse")
    assert "Desk: Customer Service" in cs
    assert "on the phone or email with the customer" in cs
    assert "Desk: Salesperson" in sales
    assert "Do not promise DC stock" in sales
    assert "Desk: Customer Service" in unknown
    assert "Desk: Salesperson" not in cs
    accounts = system_prompt_for(org, staff_role="accounts")
    purchasing = system_prompt_for(org, staff_role="purchasing")
    logistics = system_prompt_for(org, staff_role="logistics")
    assert "Accounts Receivable or Credits" in accounts
    assert "purchasing officer" in purchasing
    assert "logistics or TMS" in logistics


def test_compose_search_query_uses_prior_user_turn():
    query = compose_search_query(
        "but the product is ruined and they need to urgently replenish",
        [{"role": "user", "content": "a customer received an order with liquid spilled through it"}],
    )
    assert "liquid" in query
    assert "replenish" in query
    assert "DRILL-BIT" not in query


def test_compose_search_query_ignores_unrelated_prior_topic():
    query = compose_search_query(
        "a customer received an order with liquid which has spilled all through it how should we proceed?",
        [{"role": "user", "content": "tell me about how to process an order for a buy in item"}],
    )
    assert "buy in" not in query.lower()
    assert "spilled" in query


def test_select_chunks_prefers_damage_sop_over_buyin_returns():
    chunks = [
        RetrievedChunk(
            chunk_id="buyin",
            text="Buy-in DRILL-BIT is firm sale. Not returnable under SOP-CS-014.",
            score=0.81,
            metadata={"message_id": "buyin", "subject": "Return request DRILL-BIT — not returnable"},
        ),
        RetrievedChunk(
            chunk_id="sop",
            text="SOP-CS-018: wet cartons are damaged in transit. Raise an RA and a replacement order.",
            score=0.40,
            metadata={"message_id": "sop", "subject": "SOP-CS-018 Damaged, wet, or contaminated deliveries", "department": "policy"},
        ),
    ]
    selected = select_chunks(
        chunks,
        question="liquid spilled through the delivery the product is ruined",
        top_n=2,
        min_score=0.35,
    )
    assert selected[0].metadata["message_id"] == "sop"


def test_select_chunks_prefers_distinct_emails_and_identifiers():
    chunks = [
        _chunk("Random warehouse chatter", 0.9, "a"),
        _chunk("Same thread again", 0.88, "a"),
        _chunk("Credit note RA-24100 posted for Rivergate", 0.30, "b"),
        _chunk("Unrelated quote", 0.40, "c"),
    ]
    selected = select_chunks(chunks, question="Status of RA-24100?", top_n=3, min_score=0.35)
    ids = [item.metadata["message_id"] for item in selected]
    assert "b" in ids
    assert ids.count("a") == 1
