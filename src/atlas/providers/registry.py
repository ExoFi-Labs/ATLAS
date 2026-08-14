from __future__ import annotations

from atlas.config import Settings
from atlas.providers.auth.dev import DevAuthProvider
from atlas.providers.auth.oidc import OIDCAuthProvider
from atlas.providers.base import (
    AuthProvider,
    EmbeddingsProvider,
    LLMProvider,
    STTProvider,
    TTSProvider,
    VectorStoreProvider,
)
from atlas.providers.embeddings.sentence_transformers import SentenceTransformersEmbeddings
from atlas.providers.llm.openai_compat import OpenAICompatLLM
from atlas.providers.stt.whisper import WhisperSTT
from atlas.providers.tts.google import GoogleTTS
from atlas.providers.tts.none import NoOpTTS
from atlas.providers.vector.qdrant import QdrantVectorStore


class ProviderRegistry:
    """Central factory — swap backends via environment variables only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._llm: LLMProvider | None = None
        self._auth: AuthProvider | None = None
        self._embeddings: EmbeddingsProvider | None = None
        self._vector: VectorStoreProvider | None = None
        self._tts: TTSProvider | None = None
        self._stt: STTProvider | None = None

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            # ollama, vllm, and openai_compat share one implementation
            self._llm = OpenAICompatLLM(self.settings.llm)
        return self._llm

    @property
    def auth(self) -> AuthProvider:
        if self._auth is None:
            if self.settings.auth.provider == "oidc":
                self._auth = OIDCAuthProvider(self.settings.auth)
            else:
                self._auth = DevAuthProvider(self.settings.auth)
        return self._auth

    @property
    def embeddings(self) -> EmbeddingsProvider:
        if self._embeddings is None:
            self._embeddings = SentenceTransformersEmbeddings(self.settings.embeddings)
        return self._embeddings

    @property
    def vector(self) -> VectorStoreProvider:
        if self._vector is None:
            self._vector = QdrantVectorStore(self.settings.vector, self.settings.embeddings)
        return self._vector

    @property
    def tts(self) -> TTSProvider:
        if self._tts is None:
            if self.settings.tts.provider == "google":
                self._tts = GoogleTTS(self.settings.tts)
            else:
                self._tts = NoOpTTS()
        return self._tts

    @property
    def stt(self) -> STTProvider:
        if self._stt is None:
            if self.settings.stt.provider == "whisper":
                self._stt = WhisperSTT(self.settings.stt)
            else:
                from atlas.providers.stt.none import NoOpSTT

                self._stt = NoOpSTT()
        return self._stt


_registry: ProviderRegistry | None = None


def get_registry(settings: Settings | None = None) -> ProviderRegistry:
    global _registry
    if settings is not None:
        _registry = ProviderRegistry(settings)
    if _registry is None:
        from atlas.config import get_settings

        _registry = ProviderRegistry(get_settings())
    return _registry
