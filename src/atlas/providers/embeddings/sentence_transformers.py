from __future__ import annotations

import asyncio
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from atlas.config import EmbeddingsSettings


@lru_cache
def _load_model(model_name: str, device: str) -> SentenceTransformer:
    return SentenceTransformer(model_name, device=device)


class SentenceTransformersEmbeddings:
    def __init__(self, settings: EmbeddingsSettings) -> None:
        self.settings = settings
        self._model = _load_model(settings.model, settings.device)

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_passages([f"query: {text}"]))[0]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {text}" if not text.startswith("passage:") else text for text in texts]
        vectors = await asyncio.to_thread(
            self._model.encode,
            prefixed,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    @property
    def vector_size(self) -> int:
        dimension = getattr(self._model, "get_embedding_dimension", None)
        if callable(dimension):
            return int(dimension())
        return int(self._model.get_sentence_embedding_dimension())
