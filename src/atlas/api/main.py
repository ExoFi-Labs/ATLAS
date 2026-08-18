from __future__ import annotations

import asyncio
import re
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from atlas import __version__
from atlas.api.envutil import WRITABLE, update_env_file
from atlas.api.ollama import router as ollama_router
from atlas.config import Settings, get_settings
from atlas.ingestion.pipeline import EmailIngestionPipeline
from atlas.providers.registry import get_registry
from atlas.rag.pipeline import RAGPipeline

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEB_DIR = PROJECT_ROOT / "web"
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
ALLOWED_SUFFIXES = {".eml", ".mbox"}
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


class ChatResponseBody(BaseModel):
    answer: str
    citations: list[dict]


class SynthesizeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    speaking_rate: float | None = Field(default=None, ge=0.5, le=2.0)
    voice: str | None = None


class SettingsUpdate(BaseModel):
    values: dict[str, str]


def _group_sources(payloads: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for payload in payloads:
        key = str(payload.get("message_id") or payload.get("chunk_id"))
        item = grouped.setdefault(
            key,
            {
                "message_id": payload.get("message_id", ""),
                "subject": payload.get("subject", "(no subject)"),
                "from": payload.get("from", ""),
                "to": payload.get("to", []),
                "date": payload.get("date", ""),
                "department": payload.get("department", ""),
                "source_path": payload.get("source_path", ""),
                "thread_id": payload.get("thread_id", ""),
                "chunks": 0,
            },
        )
        item["chunks"] += 1
        if payload.get("source_path"):
            item["source_path"] = payload.get("source_path")
    return sorted(grouped.values(), key=lambda row: row.get("date") or "", reverse=True)


def _safe_filename(name: str) -> str:
    raw = Path(name or "upload.eml").name
    stem = SAFE_NAME_RE.sub("_", Path(raw).stem)[:80] or "upload"
    suffix = Path(raw).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix or '(none)'}. Use .eml or .mbox",
        )
    return f"{stem}{suffix}"


def _safe_existing_file(source_path: str) -> Path:
    if not source_path:
        raise HTTPException(status_code=404, detail="No source file path stored for this email")
    resolved = Path(source_path).resolve()
    root = PROJECT_ROOT.resolve()
    if not str(resolved).startswith(str(root)):
        raise HTTPException(status_code=403, detail="File is outside the ATLAS project")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Original .eml file is no longer on disk")
    return resolved


def _capacity(points: int, vector_size: int) -> dict:
    dims = vector_size or 384
    bytes_per_vector = dims * 4
    payload_estimate = 2500
    per_chunk = bytes_per_vector + payload_estimate
    used = points * per_chunk
    return {
        "vector_dimensions": dims,
        "bytes_per_chunk_estimate": per_chunk,
        "index_bytes_estimate": used,
        "comfortable_emails": 100_000,
        "home_pc_ceiling_emails": 1_000_000,
        "notes": [
            "Each email message is typically 1 chunk (long messages split).",
            "bge-small vectors are 384 numbers; that is about 1.5 KB plus the email text.",
            "10,000 emails ≈ 40 MB. 100,000 ≈ a few hundred MB. Fine on this PC.",
            "Around 1 million emails is when embedded Qdrant should become a Qdrant server.",
            "Answer quality is limited by the LLM context (top 5 chunks), not by how many emails you store.",
            "phi3 on a single GPU handles one active chat comfortably; more users should wait for vLLM.",
        ],
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    registry = get_registry(settings)
    pipeline = RAGPipeline(registry, settings)
    ingest_pipeline = EmailIngestionPipeline(registry, settings.ingestion)
    ingest_lock = asyncio.Lock()

    app = FastAPI(title="ATLAS", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(ollama_router)

    async def current_user(authorization: str | None = Header(default=None)):
        try:
            return await registry.auth.authenticate(authorization)
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "version": __version__,
            "providers": {
                "llm": settings.llm.provider,
                "auth": settings.auth.provider,
                "vector": settings.vector.provider,
                "tts": settings.tts.provider,
                "stt": settings.stt.provider,
            },
        }

    @app.get("/api/status")
    async def status(user=Depends(current_user)):
        stats = await registry.vector.stats()
        return {
            "version": __version__,
            "env": settings.env,
            "llm": {
                "provider": settings.llm.provider,
                "model": settings.llm.model,
                "base_url": settings.llm.base_url,
                "max_tokens": settings.llm.max_tokens,
                "temperature": settings.llm.temperature,
            },
            "embeddings": {
                "provider": settings.embeddings.provider,
                "model": settings.embeddings.model,
                "device": settings.embeddings.device,
                "vector_size": stats.get("vector_size") or 384,
            },
            "qdrant": stats,
            "rag": {
                "top_k": settings.rag.top_k,
                "top_n": settings.rag.top_n,
                "min_score": settings.rag.min_score,
            },
            "auth": {"provider": settings.auth.provider, "dev_roles": settings.auth.dev_roles},
            "tts": {"provider": settings.tts.provider, "voice": settings.tts.google_voice},
            "stt": {"provider": settings.stt.provider, "model": settings.stt.whisper_model},
            "ingestion": {
                "default_roles": settings.ingestion.default_roles,
                "default_department": settings.ingestion.default_department,
            },
            "capacity": _capacity(int(stats.get("points") or 0), int(stats.get("vector_size") or 384)),
        }

    @app.get("/api/config/public")
    async def public_config():
        return {
            "name": "ATLAS",
            "voice_enabled": settings.stt.provider != "none" or settings.tts.provider != "none",
            "tts": {
                "provider": settings.tts.provider,
                "voice": settings.tts.google_voice,
                "speaking_rate": settings.tts.speaking_rate,
            },
            "stt": {
                "provider": settings.stt.provider,
                "model": settings.stt.whisper_model,
                "vad": settings.stt.vad,
                "vad_threshold": settings.stt.vad_threshold,
                "vad_min_silence_ms": settings.stt.vad_min_silence_ms,
            },
            "auth_provider": settings.auth.provider,
        }

    @app.get("/api/sources")
    async def list_sources(user=Depends(current_user)):
        payloads = await registry.vector.list_payloads()
        sources = _group_sources(payloads)
        stats = await registry.vector.stats()
        return {
            "count": len(sources),
            "chunks": len(payloads),
            "sources": sources,
            "qdrant": stats,
            "capacity": _capacity(len(payloads), int(stats.get("vector_size") or 384)),
        }

    @app.get("/api/sources/item")
    async def get_source(id: str = Query(..., min_length=1), user=Depends(current_user)):
        payloads = [item for item in await registry.vector.list_payloads() if item.get("message_id") == id]
        if not payloads:
            raise HTTPException(status_code=404, detail="Email not found in Qdrant")
        grouped = _group_sources(payloads)[0]
        raw_available = False
        try:
            _safe_existing_file(str(grouped.get("source_path") or ""))
            raw_available = True
        except HTTPException:
            raw_available = False
        return {
            **grouped,
            "raw_available": raw_available,
            "chunks": [
                {
                    "chunk_id": item.get("chunk_id"),
                    "part_index": item.get("part_index", 0),
                    "text": item.get("text", ""),
                    "allowed_roles": item.get("allowed_roles", []),
                }
                for item in payloads
            ],
        }

    @app.get("/api/sources/raw")
    async def get_raw_source(id: str = Query(..., min_length=1), user=Depends(current_user)):
        payloads = [item for item in await registry.vector.list_payloads() if item.get("message_id") == id]
        if not payloads:
            raise HTTPException(status_code=404, detail="Email not found in Qdrant")
        path = _safe_existing_file(str(payloads[0].get("source_path") or ""))
        return PlainTextResponse(path.read_text(encoding="utf-8", errors="replace"), media_type="text/plain")

    @app.delete("/api/sources/item")
    async def delete_source(id: str = Query(..., min_length=1), user=Depends(current_user)):
        deleted = await registry.vector.delete_by_message_id(id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Email not found in Qdrant")
        return {"deleted_chunks": deleted, "message_id": id}

    @app.post("/api/sources/upload")
    async def upload_sources(
        files: list[UploadFile] = File(...),
        department: str = Form(""),
        user=Depends(current_user),
    ):
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")

        batch_dir = UPLOAD_DIR / uuid.uuid4().hex[:8]
        batch_dir.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        for upload in files:
            filename = _safe_filename(upload.filename or "upload.eml")
            dest = batch_dir / filename
            dest.write_bytes(await upload.read())
            saved.append(filename)

        async with ingest_lock:
            result = await ingest_pipeline.ingest(batch_dir, department=department or None)

        payloads = await registry.vector.list_payloads()
        return {
            "indexed_files": result.files,
            "messages": result.messages,
            "chunks": result.chunks,
            "attachments": result.attachments,
            "attachments_skipped": result.attachments_skipped,
            "pii_hits": result.pii_hits,
            "saved": saved,
            "library": {"count": len(_group_sources(payloads)), "chunks": len(payloads)},
        }

    @app.get("/api/settings")
    async def get_app_settings(user=Depends(current_user)):
        return {
            "writable": sorted(WRITABLE),
            "values": {
                "ATLAS_LLM__MODEL": settings.llm.model,
                "ATLAS_LLM__BASE_URL": settings.llm.base_url,
                "ATLAS_LLM__MAX_TOKENS": str(settings.llm.max_tokens),
                "ATLAS_LLM__TEMPERATURE": str(settings.llm.temperature),
                "ATLAS_RAG__TOP_K": str(settings.rag.top_k),
                "ATLAS_RAG__TOP_N": str(settings.rag.top_n),
                "ATLAS_RAG__MIN_SCORE": str(settings.rag.min_score),
                "ATLAS_TTS__PROVIDER": settings.tts.provider,
                "ATLAS_TTS__GOOGLE_VOICE": settings.tts.google_voice,
                "ATLAS_TTS__SPEAKING_RATE": str(settings.tts.speaking_rate),
                "ATLAS_STT__PROVIDER": settings.stt.provider,
                "ATLAS_STT__WHISPER_MODEL": settings.stt.whisper_model,
                "ATLAS_STT__VAD": "true" if settings.stt.vad else "false",
                "ATLAS_STT__VAD_THRESHOLD": str(settings.stt.vad_threshold),
                "ATLAS_STT__VAD_MIN_SILENCE_MS": str(settings.stt.vad_min_silence_ms),
                "ATLAS_INGESTION__DEFAULT_ROLES": settings.ingestion.default_roles,
                "ATLAS_INGESTION__DEFAULT_DEPARTMENT": settings.ingestion.default_department,
                "ATLAS_AUTH__DEV_ROLES": settings.auth.dev_roles,
            },
            "restart_required_for": [
                "ATLAS_LLM__BASE_URL",
                "ATLAS_TTS__PROVIDER",
                "ATLAS_STT__PROVIDER",
                "ATLAS_STT__WHISPER_MODEL",
            ],
        }

    @app.post("/api/settings")
    async def save_app_settings(body: SettingsUpdate, user=Depends(current_user)):
        written = update_env_file(body.values)
        if "ATLAS_LLM__MODEL" in written:
            settings.llm.model = body.values["ATLAS_LLM__MODEL"]
        if "ATLAS_LLM__BASE_URL" in written:
            settings.llm.base_url = body.values["ATLAS_LLM__BASE_URL"]
        if "ATLAS_LLM__MAX_TOKENS" in written:
            settings.llm.max_tokens = int(float(body.values["ATLAS_LLM__MAX_TOKENS"]))
        if "ATLAS_LLM__TEMPERATURE" in written:
            settings.llm.temperature = float(body.values["ATLAS_LLM__TEMPERATURE"])
        if "ATLAS_RAG__TOP_K" in written:
            settings.rag.top_k = int(float(body.values["ATLAS_RAG__TOP_K"]))
        if "ATLAS_RAG__TOP_N" in written:
            settings.rag.top_n = int(float(body.values["ATLAS_RAG__TOP_N"]))
        if "ATLAS_RAG__MIN_SCORE" in written:
            settings.rag.min_score = float(body.values["ATLAS_RAG__MIN_SCORE"])
        if "ATLAS_TTS__PROVIDER" in written:
            settings.tts.provider = body.values["ATLAS_TTS__PROVIDER"]  # type: ignore[assignment]
        if "ATLAS_TTS__GOOGLE_VOICE" in written:
            settings.tts.google_voice = body.values["ATLAS_TTS__GOOGLE_VOICE"]
        if "ATLAS_TTS__SPEAKING_RATE" in written:
            settings.tts.speaking_rate = float(body.values["ATLAS_TTS__SPEAKING_RATE"])
        if "ATLAS_STT__PROVIDER" in written:
            settings.stt.provider = body.values["ATLAS_STT__PROVIDER"]  # type: ignore[assignment]
        if "ATLAS_STT__WHISPER_MODEL" in written:
            settings.stt.whisper_model = body.values["ATLAS_STT__WHISPER_MODEL"]
        if "ATLAS_STT__VAD" in written:
            settings.stt.vad = body.values["ATLAS_STT__VAD"].strip().lower() in {"1", "true", "yes", "on"}
        if "ATLAS_STT__VAD_THRESHOLD" in written:
            settings.stt.vad_threshold = float(body.values["ATLAS_STT__VAD_THRESHOLD"])
        if "ATLAS_STT__VAD_MIN_SILENCE_MS" in written:
            settings.stt.vad_min_silence_ms = int(float(body.values["ATLAS_STT__VAD_MIN_SILENCE_MS"]))
        if "ATLAS_INGESTION__DEFAULT_ROLES" in written:
            settings.ingestion.default_roles = body.values["ATLAS_INGESTION__DEFAULT_ROLES"]
        if "ATLAS_INGESTION__DEFAULT_DEPARTMENT" in written:
            settings.ingestion.default_department = body.values["ATLAS_INGESTION__DEFAULT_DEPARTMENT"]
        if "ATLAS_AUTH__DEV_ROLES" in written:
            settings.auth.dev_roles = body.values["ATLAS_AUTH__DEV_ROLES"]
        return {"saved": written}

    @app.post("/api/chat", response_model=ChatResponseBody)
    async def chat(body: ChatRequest, user=Depends(current_user)):
        result = await pipeline.answer(body.message, user, history=body.history)
        return ChatResponseBody(
            answer=result.content,
            citations=[
                {
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                    "metadata": c.metadata,
                    "preview": c.text[:240],
                    "subject": c.metadata.get("subject", ""),
                    "from": c.metadata.get("from", ""),
                    "message_id": c.metadata.get("message_id", ""),
                }
                for c in result.citations
            ],
        )

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatRequest, user=Depends(current_user)):
        async def event_generator():
            async for item in pipeline.stream_answer(body.message, user, history=body.history):
                if isinstance(item, str):
                    yield {"event": "token", "data": item}
                elif isinstance(item, dict) and item.get("event") == "citations":
                    yield {"event": "citations", "data": str(item["data"])}
            yield {"event": "done", "data": "ok"}

        return EventSourceResponse(event_generator())

    @app.post("/api/voice/transcribe")
    async def transcribe(file: UploadFile = File(...), user=Depends(current_user)):
        audio = await file.read()
        if not audio:
            raise HTTPException(status_code=400, detail="Empty audio")
        try:
            text = await registry.stt.transcribe(audio, mime_type=file.content_type or "audio/webm")
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Transcription failed: {exc}") from exc
        return {
            "text": text,
            "vad": settings.stt.vad,
            "engine": "silero+whisper" if settings.stt.provider == "whisper" else settings.stt.provider,
        }

    @app.post("/api/voice/synthesize")
    async def synthesize(body: SynthesizeRequest, user=Depends(current_user)):
        try:
            audio = await registry.tts.synthesize(
                body.message,
                speaking_rate=body.speaking_rate,
                voice=body.voice,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"TTS failed: {exc}") from exc
        return Response(content=audio, media_type="audio/mpeg")

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
