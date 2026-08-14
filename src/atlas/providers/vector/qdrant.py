from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from atlas.config import EmbeddingsSettings, VectorSettings
from atlas.providers.base import RetrievedChunk

_PAYLOAD_INDEXES = ("allowed_roles", "department", "thread_id", "subject")


class QdrantVectorStore:
    def __init__(self, settings: VectorSettings, embeddings_settings: EmbeddingsSettings) -> None:
        self.settings = settings
        if settings.path:
            self._client = AsyncQdrantClient(path=settings.path)
        else:
            self._client = AsyncQdrantClient(url=settings.url)
        self._embeddings_settings = embeddings_settings

    async def ensure_collection(self, vector_size: int) -> None:
        exists = await self._client.collection_exists(self.settings.collection)
        if not exists:
            await self._client.create_collection(
                collection_name=self.settings.collection,
                vectors_config=qmodels.VectorParams(size=vector_size, distance=qmodels.Distance.COSINE),
            )
        if not self.settings.path:
            for field_name in _PAYLOAD_INDEXES:
                try:
                    await self._client.create_payload_index(
                        collection_name=self.settings.collection,
                        field_name=field_name,
                        field_schema=qmodels.PayloadSchemaType.KEYWORD,
                    )
                except (UnexpectedResponse, ValueError):
                    continue

    async def upsert(self, points: list[tuple[str, list[float], dict]]) -> None:
        await self._client.upsert(
            collection_name=self.settings.collection,
            points=[
                qmodels.PointStruct(id=point_id, vector=vector, payload=payload)
                for point_id, vector, payload in points
            ],
        )

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        if not await self._client.collection_exists(self.settings.collection):
            return []
        qdrant_filter = self._build_filter(filters or {})
        results = await self._client.query_points(
            collection_name=self.settings.collection,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        chunks: list[RetrievedChunk] = []
        for point in results.points:
            payload = point.payload or {}
            chunks.append(
                RetrievedChunk(
                    chunk_id=str(point.id),
                    text=str(payload.get("text", "")),
                    score=float(point.score or 0.0),
                    metadata={k: v for k, v in payload.items() if k != "text"},
                )
            )
        return chunks

    async def list_payloads(self, *, limit: int = 1000) -> list[dict]:
        if not await self._client.collection_exists(self.settings.collection):
            return []
        payloads: list[dict] = []
        offset = None
        while len(payloads) < limit:
            points, offset = await self._client.scroll(
                collection_name=self.settings.collection,
                limit=min(100, limit - len(payloads)),
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = dict(point.payload or {})
                payload["chunk_id"] = str(point.id)
                payloads.append(payload)
            if offset is None:
                break
        return payloads

    async def stats(self) -> dict:
        if not await self._client.collection_exists(self.settings.collection):
            return {
                "exists": False,
                "points": 0,
                "vector_size": 0,
                "status": "missing",
                "collection": self.settings.collection,
                "mode": "embedded" if self.settings.path else "server",
                "path": self.settings.path,
                "url": self.settings.url,
            }
        info = await self._client.get_collection(self.settings.collection)
        vector_size = 0
        try:
            vectors = info.config.params.vectors
            vector_size = getattr(vectors, "size", None) or 0
            if not vector_size and isinstance(vectors, dict) and vectors:
                first = next(iter(vectors.values()))
                vector_size = getattr(first, "size", 0) or 0
        except Exception:
            vector_size = 0
        return {
            "exists": True,
            "points": int(info.points_count or 0),
            "indexed_vectors": int(getattr(info, "indexed_vectors_count", 0) or 0),
            "vector_size": int(vector_size or 0),
            "status": str(info.status),
            "collection": self.settings.collection,
            "mode": "embedded" if self.settings.path else "server",
            "path": self.settings.path,
            "url": self.settings.url,
        }

    async def delete_by_message_id(self, message_id: str) -> int:
        payloads = await self.list_payloads()
        ids = [item["chunk_id"] for item in payloads if item.get("message_id") == message_id]
        if not ids:
            return 0
        await self._client.delete(
            collection_name=self.settings.collection,
            points_selector=qmodels.PointIdsList(points=ids),
        )
        return len(ids)

    def _build_filter(self, filters: dict) -> qmodels.Filter | None:
        roles = filters.get("roles") or []
        if not roles:
            return None

        return qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="allowed_roles",
                    match=qmodels.MatchAny(any=roles),
                )
            ]
        )
