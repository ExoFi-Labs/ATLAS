from __future__ import annotations

from atlas.config import RAGSettings
from atlas.providers.base import ChatMessage, ChatResponse, RetrievedChunk, UserContext
from atlas.providers.registry import ProviderRegistry

SYSTEM_PROMPT = """You are ATLAS, an internal company assistant.
Answer using ONLY the provided source excerpts from company email records.
If the sources do not contain enough information, say so clearly.
Cite sources inline as [1], [2], etc.
Keep answers concise unless the user asks for detail."""


class RAGPipeline:
    def __init__(self, registry: ProviderRegistry, settings: RAGSettings) -> None:
        self.registry = registry
        self.settings = settings

    async def answer(self, question: str, user: UserContext) -> ChatResponse:
        query_vector = await self.registry.embeddings.embed_query(question)
        chunks = await self.registry.vector.search(
            query_vector,
            top_k=self.settings.top_k,
            filters={"roles": user.roles},
        )
        ranked = self._select_chunks(chunks)
        messages = self._build_messages(question, ranked)
        content = await self.registry.llm.chat(messages)
        if not isinstance(content, str):
            raise TypeError("Expected non-streaming LLM response")

        return ChatResponse(content=content, citations=ranked)

    async def stream_answer(self, question: str, user: UserContext):
        query_vector = await self.registry.embeddings.embed_query(question)
        chunks = await self.registry.vector.search(
            query_vector,
            top_k=self.settings.top_k,
            filters={"roles": user.roles},
        )
        ranked = self._select_chunks(chunks)
        messages = self._build_messages(question, ranked)
        stream = await self.registry.llm.chat(messages, stream=True)
        if isinstance(stream, str):
            raise TypeError("Expected streaming LLM response")

        async for token in stream:
            yield token

        yield {"event": "citations", "data": [self._chunk_to_dict(chunk) for chunk in ranked]}

    def _select_chunks(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        filtered = [chunk for chunk in chunks if chunk.score >= self.settings.min_score]
        return filtered[: self.settings.top_n]

    def _build_messages(self, question: str, chunks: list[RetrievedChunk]) -> list[ChatMessage]:
        if chunks:
            context = "\n\n".join(
                f"[{index}] {chunk.text}\n(metadata: {chunk.metadata})"
                for index, chunk in enumerate(chunks, start=1)
            )
        else:
            context = "No relevant sources were retrieved."

        return [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Sources:\n{context}\n\nQuestion: {question}",
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
