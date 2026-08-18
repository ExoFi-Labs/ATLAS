from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from atlas.config import OrgSettings, RAGSettings, Settings
from atlas.providers.base import ChatMessage, ChatResponse, RetrievedChunk, UserContext
from atlas.providers.registry import ProviderRegistry
from atlas.textprep import for_display

IDENTIFIER_RE = re.compile(
    r"\b(?:RA|CN|INV|PO|SO|DN|ASN)[- ]?\d{3,}\b|\b45\d{6,}\b|\bHMD[- ]?\d{3,}\b",
    re.IGNORECASE,
)
SOP_RE = re.compile(r"\bSOP-[A-Z]+-\d+\b", re.IGNORECASE)
EXAMPLE_KEY_RE = re.compile(r"\d+")

_QUERY_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("spill", "spilled", "wet", "leaked", "damaged", "ruined", "carton crushed", "contaminated"), "damaged in transit wet carton leaked liquid Helix error replacement RA SOP-CS-018"),
    (("quote", "quotation", "rfq", "pricing", "price list"), "quotation pricing contract price RFQ"),
    (("credit", "return", "ra ", "credit note"), "credit note return authorisation RA G2 warehouse"),
    (("buy-in", "buy in", "direct ship", "drop ship"), "buy-in special buy direct ship not held in DC"),
    (("invoice", "gst", "tax invoice"), "tax invoice GST price variance accounts receivable"),
    (("backorder", "bo ", "awaiting stock"), "backorder ATP awaiting stock eta allocation"),
    (("delivery", "eta", "consignment", "where is"), "delivery ETA consignment POD courier tracking"),
    (("warehouse", "pick", "short pick", "pod"), "warehouse pick pack POD consignment"),
    (("purchasing", "supplier", "lead time"), "purchasing supplier inbound ASN lead time"),
    (("order", "sales order", "so "), "sales order SAP ATP allocation"),
)
FOLLOW_UP_RE = re.compile(
    r"^(but|and|so|also|then|ok[, ]|okay[, ]|what about|how about|and then)\b",
    re.IGNORECASE,
)
DAMAGE_TERMS = (
    "spill",
    "spilled",
    "wet",
    "leak",
    "leaked",
    "damaged",
    "ruined",
    "contaminated",
    "crushed",
)

STAFF_ROLES: dict[str, tuple[str, str]] = {
    "customer_service": (
        "Customer Service",
        """Desk: Customer Service.
You are briefing a CS agent on the phone or email with the customer.
- Say what to tell the customer, then the SAP / email action, then who to copy.
- Do not verbally agree credits, new prices, or courier ETAs that Credits, AR, or Logistics own.
- Hand off with the order, RA, invoice, or consignment number. Name the owning team once.""",
    ),
    "accounts": (
        "Accounts",
        """Desk: Accounts (AR and Credits).
You are briefing Accounts Receivable or Credits, not the person on the phone.
- Focus on invoices, G2 credit notes, tax codes, stop-supply, and RA receipt posting.
- CS must not verbally agree a new price. AR checks the SAP condition against the quote.
- Do not tell anyone to ignore a duplicate invoice — reverse the later document.
- Credits issues the credit after warehouse receipt or documented destruction.""",
    ),
    "sales": (
        "Salesperson",
        """Desk: Salesperson.
You are briefing a salesperson talking to the account.
- Lead with what they can promise: quote validity, contract vs list, MOQ, lead time, firm-sale flags.
- Do not promise DC stock or same-day dispatch on buy-in or direct-ship lines.
- Price queries on an existing invoice go to AR with the invoice number — that is not a new quote.
- Theatre or delivery dates belong on the PO, not as a casual promise.""",
    ),
    "purchasing": (
        "Purchasing",
        """Desk: Purchasing.
You are briefing a purchasing officer.
- Focus on buy-in flags, supplier PO, inbound ETA, theatre dates on the PO, and ASN.
- Do not promise Helix DC stock for a non-stocked line. Firm sale once the supplier PO is sent.
- Direct ship POD comes from the supplier, not a Helix consignment.
- If the customer later wants the item as a stocked line, that is a Purchasing decision — do not keep a silent overstock in the DC.""",
    ),
    "logistics": (
        "Logistics",
        """Desk: Logistics.
You are briefing logistics or TMS.
- First check SAP GI date and the TMS consignment. Never invent an ETA.
- If the courier scan has not moved for 24 hours, Logistics chases the carrier. CS should not guess.
- Helix fleet and StarTrack POD sits on the consignment; direct-ship POD is the supplier’s.
- Cold chain out of range: quarantine and call Quality. Do not tell the customer to use the stock.
- Failed delivery: rebook once. A second fail is charged.""",
    ),
}
DEFAULT_STAFF_ROLE = "customer_service"


def normalize_staff_role(staff_role: str | None) -> str:
    key = (staff_role or DEFAULT_STAFF_ROLE).strip().lower()
    return key if key in STAFF_ROLES else DEFAULT_STAFF_ROLE


def system_prompt_for(org: OrgSettings, length: str = "regular", staff_role: str = DEFAULT_STAFF_ROLE) -> str:
    role_key = normalize_staff_role(staff_role)
    _label, role_rules = STAFF_ROLES[role_key]
    length_rules = (
        """Reply length: SHORT.
- A few short sentences, as if you are talking to a colleague at the desk: direct and concise.
- Cover the action, the owning team, and any number they need. Skip the rest.
- Do not use bullets, numbered lists, or section headings.
- Cite at most two sources. No recap, no “next steps” section, no example SKUs or prices."""
        if length == "short"
        else """Reply length: REGULAR.
- Full operational answer: what to do, who owns it, and missing details to confirm.
- Numbered steps with a short section title on its own line, then the instruction."""
    )
    return f"""You are ATLAS, the internal staff assistant for {org.name} ({org.short_name}).
{org.description}

Answer from the source emails below. Staff need a direct, operational answer: what to do, who owns it, and any order / RA / invoice numbers.
{role_rules}
{length_rules}
- Write plain text only. Do not use markdown, asterisks, underscores, or bold. No ** wrapping.
- The current staff question is the case. Earlier chat may be a different topic — do not carry SKUs, order numbers, or policies from an earlier topic into this one.
- If this question (or the last staff message) is about leakage, wet cartons, or ruined product, use the damaged-in-transit SOP. That is Helix/carrier error: raise an RA and a replacement order. Do not apply buy-in firm-sale / no-return rules.
- Lead with SOP / policy sources. Other emails are examples of different customers — do not copy their SKUs, prices, or order numbers onto this case.
- If the user has not named an SKU or order, do not pick one from the examples.
- Never invent email addresses, teams, SOPs, or document numbers that are not in the sources.
- If several emails disagree, prefer the SOP, then the latest dated reply.
- Cite sources inline as [1], [2]."""


def _turns(history: list[Any] | None) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    for item in history or []:
        if hasattr(item, "role"):
            role, content = str(item.role), str(item.content or "")
        else:
            role, content = str(item.get("role") or ""), str(item.get("content") or "")
        if role in {"user", "assistant"} and content.strip():
            turns.append((role, content.strip()))
    return turns[-6:]


def _looks_like_follow_up(question: str) -> bool:
    text = question.strip()
    if not text:
        return False
    if FOLLOW_UP_RE.match(text):
        return True
    lowered = text.lower()
    if any(token in lowered for token in (" they ", "the customer", "this order", "that order", "the product", "this case")):
        return True
    return len(text.split()) <= 16


def compose_search_query(question: str, history: list[Any] | None = None) -> str:
    """Use prior *user* questions only — assistant replies contain leftover SKUs that poison search."""
    users = [content for role, content in _turns(history) if role == "user"]
    current = question.strip()
    if users and _looks_like_follow_up(current):
        return f"{users[-1]} {current}".strip()[:1200]
    return current


def retrieval_queries(question: str, history: list[Any] | None = None) -> list[str]:
    text = compose_search_query(question, history)
    if not text:
        return [question]
    queries = [text]
    lowered = text.lower()
    for needles, hint in _QUERY_HINTS:
        if any(needle in lowered for needle in needles):
            extra = f"{text} {hint}"
            if extra not in queries:
                queries.append(extra)
            break
    return queries[:2]


def extract_identifiers(text: str) -> list[str]:
    return [item.replace(" ", "").upper() for item in IDENTIFIER_RE.findall(text or "")]


def compact_chunk_text(text: str, max_chars: int) -> str:
    body = (text or "").strip()
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 1].rstrip() + "…"


def _is_policy(chunk: RetrievedChunk) -> bool:
    subject = str(chunk.metadata.get("subject") or "")
    department = str(chunk.metadata.get("department") or "").lower()
    return department == "policy" or subject.upper().startswith("SOP-") or bool(SOP_RE.search(subject))


def _example_key(chunk: RetrievedChunk) -> str:
    subject = EXAMPLE_KEY_RE.sub("", str(chunk.metadata.get("subject") or "")).lower()
    return re.sub(r"\s+", " ", subject).strip()[:48]


def select_chunks(
    chunks: list[RetrievedChunk],
    *,
    question: str,
    top_n: int,
    min_score: float,
) -> list[RetrievedChunk]:
    ids = extract_identifiers(question)
    damage_query = any(term in question.lower() for term in DAMAGE_TERMS)
    scored: list[tuple[float, RetrievedChunk]] = []
    for chunk in chunks:
        haystack = f"{chunk.text} {chunk.metadata}".upper().replace(" ", "")
        hits = sum(1 for item in ids if item in haystack)
        floor = min_score - 0.12 if hits else min_score
        if chunk.score < floor:
            continue
        rank = chunk.score + hits * 0.15
        if _is_policy(chunk):
            rank += 0.12
        blob = f"{chunk.text} {chunk.metadata.get('subject', '')}".lower()
        if damage_query:
            if "sop-cs-018" in blob or "damaged in transit" in blob or "wet carton" in blob:
                rank += 0.28
            elif "firm sale" in blob or "not returnable" in blob or "buy-in" in blob:
                rank -= 0.22
        scored.append((rank, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected: list[RetrievedChunk] = []
    seen_messages: set[str] = set()
    example_counts: dict[str, int] = {}
    for _rank, chunk in scored:
        message_id = str(chunk.metadata.get("message_id") or chunk.chunk_id)
        if message_id in seen_messages:
            continue
        key = _example_key(chunk)
        if not _is_policy(chunk) and example_counts.get(key, 0) >= 2:
            continue
        selected.append(chunk)
        seen_messages.add(message_id)
        example_counts[key] = example_counts.get(key, 0) + 1
        if len(selected) >= top_n:
            break
    return selected


class RAGPipeline:
    def __init__(self, registry: ProviderRegistry, settings: Settings | RAGSettings) -> None:
        self.registry = registry
        if isinstance(settings, RAGSettings):
            self.rag = settings
            self.org = OrgSettings()
        else:
            self.rag = settings.rag
            self.org = settings.org

    async def answer(
        self,
        question: str,
        user: UserContext,
        history: list[Any] | None = None,
        length: str = "regular",
        staff_role: str = DEFAULT_STAFF_ROLE,
    ) -> ChatResponse:
        chunks = await self._retrieve(question, user, history)
        search_text = compose_search_query(question, history)
        ranked = select_chunks(
            chunks,
            question=search_text,
            top_n=self.rag.top_n,
            min_score=self.rag.min_score,
        )
        messages = self._build_messages(
            question, ranked, history, length=length, staff_role=staff_role
        )
        content = await self.registry.llm.chat(messages)
        if not isinstance(content, str):
            raise TypeError("Expected non-streaming LLM response")
        return ChatResponse(content=for_display(content), citations=ranked)

    async def stream_answer(
        self,
        question: str,
        user: UserContext,
        history: list[Any] | None = None,
        length: str = "regular",
        staff_role: str = DEFAULT_STAFF_ROLE,
    ) -> AsyncIterator:
        chunks = await self._retrieve(question, user, history)
        search_text = compose_search_query(question, history)
        ranked = select_chunks(
            chunks,
            question=search_text,
            top_n=self.rag.top_n,
            min_score=self.rag.min_score,
        )
        messages = self._build_messages(
            question, ranked, history, length=length, staff_role=staff_role
        )
        stream = await self.registry.llm.chat(messages, stream=True)
        if isinstance(stream, str):
            raise TypeError("Expected streaming LLM response")
        async for token in stream:
            yield token
        yield {"event": "citations", "data": [self._chunk_to_dict(chunk) for chunk in ranked]}

    async def _retrieve(
        self,
        question: str,
        user: UserContext,
        history: list[Any] | None = None,
    ) -> list[RetrievedChunk]:
        merged: dict[str, RetrievedChunk] = {}
        for query in retrieval_queries(question, history):
            vector = await self.registry.embeddings.embed_query(query)
            hits = await self.registry.vector.search(
                vector,
                top_k=self.rag.top_k,
                filters={"roles": user.roles},
            )
            for chunk in hits:
                previous = merged.get(chunk.chunk_id)
                if previous is None or chunk.score > previous.score:
                    merged[chunk.chunk_id] = chunk
        return list(merged.values())

    def _build_messages(
        self,
        question: str,
        chunks: list[RetrievedChunk],
        history: list[Any] | None = None,
        length: str = "regular",
        staff_role: str = DEFAULT_STAFF_ROLE,
    ) -> list[ChatMessage]:
        if chunks:
            context = "\n\n".join(
                f"[{index}] {compact_chunk_text(chunk.text, self.rag.max_chunk_chars)}"
                for index, chunk in enumerate(chunks, start=1)
            )
        else:
            context = "No relevant sources were retrieved."

        conversation = ""
        prior_users = [content for role, content in _turns(history) if role == "user"][-2:]
        if prior_users:
            lines = [content if len(content) <= 280 else content[:279] + "…" for content in prior_users]
            conversation = "Earlier staff questions (may be a different case):\n- " + "\n- ".join(lines) + "\n\n"

        return [
            ChatMessage(role="system", content=system_prompt_for(self.org, length, staff_role)),
            ChatMessage(
                role="user",
                content=(
                    f"{conversation}"
                    f"Source emails (each [n] is a different message; example SKUs are not this case unless named by staff):\n{context}\n\n"
                    f"Staff question: {question}"
                ),
            ),
        ]

    @staticmethod
    def _chunk_to_dict(chunk: RetrievedChunk) -> dict:
        return {
            "chunk_id": chunk.chunk_id,
            "score": chunk.score,
            "metadata": chunk.metadata,
            "preview": chunk.text[:240],
        }
