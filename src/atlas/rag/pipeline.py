from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Any

from atlas.config import OrgSettings, RAGSettings, Settings
from atlas.providers.base import ChatMessage, ChatResponse, RetrievedChunk, UserContext
from atlas.providers.registry import ProviderRegistry

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


def system_prompt_for(org: OrgSettings) -> str:
    return f"""You are ATLAS, the internal staff assistant for {org.name} ({org.short_name}).
{org.description}

Answer from the source emails below. Staff need a direct, operational answer: what to do, who owns it, and any order / RA / invoice numbers.
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
    ) -> ChatResponse:
        chunks = await self._retrieve(question, user, history)
        search_text = compose_search_query(question, history)
        ranked = select_chunks(
            chunks,
            question=search_text,
            top_n=self.rag.top_n,
            min_score=self.rag.min_score,
        )
        messages = self._build_messages(question, ranked, history)
        content = await self.registry.llm.chat(messages)
        if not isinstance(content, str):
            raise TypeError("Expected non-streaming LLM response")
        return ChatResponse(content=content, citations=ranked)

    async def stream_answer(
        self,
        question: str,
        user: UserContext,
        history: list[Any] | None = None,
    ) -> AsyncIterator:
        chunks = await self._retrieve(question, user, history)
        search_text = compose_search_query(question, history)
        ranked = select_chunks(
            chunks,
            question=search_text,
            top_n=self.rag.top_n,
            min_score=self.rag.min_score,
        )
        messages = self._build_messages(question, ranked, history)
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
            ChatMessage(role="system", content=system_prompt_for(self.org)),
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
