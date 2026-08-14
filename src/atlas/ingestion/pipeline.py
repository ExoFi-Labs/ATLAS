from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from atlas.config import IngestionSettings
from atlas.ingestion.chunk import chunk_messages
from atlas.ingestion.clean import clean_messages
from atlas.ingestion.models import EmailChunk
from atlas.ingestion.parse import parse_path
from atlas.ingestion.pii import RegexPIIScrubber
from atlas.providers.registry import ProviderRegistry


@dataclass
class IngestResult:
    files: int = 0
    messages: int = 0
    chunks: int = 0
    skipped_empty: int = 0
    pii_hits: dict[str, int] = field(default_factory=dict)
    dry_run: bool = False


class EmailIngestionPipeline:
    def __init__(self, registry: ProviderRegistry, settings: IngestionSettings) -> None:
        self.registry = registry
        self.settings = settings
        self.scrubber = RegexPIIScrubber()

    async def ingest(
        self,
        path: Path,
        *,
        department: str | None = None,
        roles: list[str] | None = None,
        dry_run: bool = False,
    ) -> IngestResult:
        parsed = parse_path(path)
        cleaned = clean_messages(parsed, scrubber=self.scrubber)
        allowed_roles = roles or _split(self.settings.default_roles)
        department_name = department or self.settings.default_department
        chunks = chunk_messages(
            cleaned,
            department=department_name,
            allowed_roles=allowed_roles,
            max_tokens=self.settings.max_chunk_tokens,
        )

        result = IngestResult(
            files=len({item.source_path.split("#", 1)[0] for item in parsed}),
            messages=len(parsed),
            chunks=len(chunks),
            skipped_empty=sum(1 for item in cleaned if not item.body),
            pii_hits=_merge_pii(cleaned),
            dry_run=dry_run,
        )
        if dry_run or not chunks:
            return result

        await self._index(chunks)
        return result

    async def _index(self, chunks: list[EmailChunk]) -> None:
        vector_size = self.registry.embeddings.vector_size
        await self.registry.vector.ensure_collection(int(vector_size))
        batch_size = 32
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = await self.registry.embeddings.embed_passages([chunk.text for chunk in batch])
            points = []
            for chunk, vector in zip(batch, vectors):
                payload = {"text": chunk.text, **chunk.metadata}
                points.append((chunk.chunk_id, vector, payload))
            await self.registry.vector.upsert(points)


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _merge_pii(cleaned) -> dict[str, int]:
    totals: dict[str, int] = {}
    for message in cleaned:
        for key, count in message.pii_hits.items():
            totals[key] = totals.get(key, 0) + count
    return totals
