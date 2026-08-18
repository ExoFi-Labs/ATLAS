from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import uvicorn

from atlas.config import get_settings
from atlas.ingestion.pipeline import EmailIngestionPipeline
from atlas.providers.registry import get_registry


def main() -> None:
    parser = argparse.ArgumentParser(prog="atlas", description="ATLAS on-premises company assistant")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("serve", help="Start the ATLAS API and chat UI")

    ingest = sub.add_parser("ingest", help="Parse, clean, chunk, and index emails")
    ingest.add_argument("path", type=Path, help="File or directory of .eml / .mbox files")
    ingest.add_argument("--department", default=None, help="Department tag stored on chunks")
    ingest.add_argument(
        "--roles",
        default=None,
        help="Comma-separated allowed_roles for RBAC filters (default: all-staff)",
    )
    ingest.add_argument("--dry-run", action="store_true", help="Parse and chunk without writing to Qdrant")
    ingest.add_argument(
        "--replace",
        action="store_true",
        help="Delete the existing Qdrant collection before indexing this path",
    )

    args = parser.parse_args()
    if args.command == "ingest":
        asyncio.run(_ingest(args))
        return
    _serve()


def _serve() -> None:
    settings = get_settings()
    # Embedded Qdrant locks the local DB to one process — reload would open it twice.
    reload = settings.env == "development" and not settings.vector.path
    uvicorn.run(
        "atlas.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=reload,
        log_level=settings.log_level,
    )


async def _ingest(args: argparse.Namespace) -> None:
    path = args.path.expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")

    settings = get_settings()
    registry = get_registry(settings)
    pipeline = EmailIngestionPipeline(registry, settings.ingestion)
    roles = [item.strip() for item in args.roles.split(",")] if args.roles else None
    if args.replace and not args.dry_run:
        vector_size = int(registry.embeddings.vector_size)
        await registry.vector.recreate_collection(vector_size)
        print(f"Replaced Qdrant collection {settings.vector.collection}")
    subdirs = sorted(p for p in path.iterdir() if p.is_dir()) if path.is_dir() else []
    targets = [(folder, args.department or folder.name) for folder in subdirs] if subdirs else [(path, args.department)]
    totals = {"files": 0, "messages": 0, "chunks": 0}
    for target, department in targets:
        result = await pipeline.ingest(
            target,
            department=department,
            roles=roles,
            dry_run=args.dry_run,
        )
        mode = "dry-run" if result.dry_run else "indexed"
        label = target.name if target.is_dir() else str(target)
        print(f"ATLAS ingest ({mode}) {label} dept={department or settings.ingestion.default_department}")
        print(f"  files:    {result.files}")
        print(f"  messages: {result.messages}")
        print(f"  chunks:   {result.chunks}")
        totals["files"] += result.files
        totals["messages"] += result.messages
        totals["chunks"] += result.chunks
    if len(targets) > 1:
        print(f"TOTAL files={totals['files']} messages={totals['messages']} chunks={totals['chunks']}")


if __name__ == "__main__":
    main()
