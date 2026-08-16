from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass(frozen=True)
class UserContext:
    user_id: str
    roles: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    text: str
    score: float
    metadata: dict


@dataclass(frozen=True)
class ChatResponse:
    content: str
    citations: list[RetrievedChunk]


class AuthProvider(Protocol):
    async def authenticate(self, authorization: str | None) -> UserContext: ...

    async def get_login_url(self) -> str | None: ...


class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        stream: bool = False,
    ) -> str | AsyncIterator[str]: ...


class EmbeddingsProvider(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def vector_size(self) -> int: ...


class VectorStoreProvider(Protocol):
    async def ensure_collection(self, vector_size: int) -> None: ...

    async def upsert(self, points: list[tuple[str, list[float], dict]]) -> None: ...

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]: ...

    async def list_payloads(self, *, limit: int = 1000) -> list[dict]: ...

    async def stats(self) -> dict: ...

    async def delete_by_message_id(self, message_id: str) -> int: ...


class TTSProvider(Protocol):
    async def synthesize(
        self,
        text: str,
        *,
        speaking_rate: float | None = None,
        voice: str | None = None,
    ) -> bytes: ...


class STTProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, *, mime_type: str = "audio/wav") -> str: ...
