"""Email ingestion: parse threads, scrub PII, chunk, and index into the vector store."""

from atlas.ingestion.pipeline import EmailIngestionPipeline, IngestResult

__all__ = ["EmailIngestionPipeline", "IngestResult"]
