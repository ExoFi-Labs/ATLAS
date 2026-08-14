from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from atlas.config import get_settings
from atlas.ollama_catalog import CATALOG, search_catalog

router = APIRouter(prefix="/api/ollama", tags=["ollama"])


class ModelName(BaseModel):
    model: str = Field(min_length=1, max_length=200)


def ollama_root() -> str:
    base = get_settings().llm.base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base.rstrip("/")


async def _ollama(method: str, path: str, timeout: float = 30.0, **kwargs) -> httpx.Response:
    url = f"{ollama_root()}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, **kwargs)
    except httpx.ConnectError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is not reachable at {ollama_root()}. Is Ollama running?",
        ) from exc
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text[:500])
    return response


@router.get("/status")
async def ollama_status():
    try:
        tags = await _ollama("GET", "/api/tags")
        running = await _ollama("GET", "/api/ps")
    except HTTPException as exc:
        if exc.status_code == 503:
            return {
                "online": False,
                "root": ollama_root(),
                "models": [],
                "running": [],
                "error": exc.detail,
            }
        raise
    return {
        "online": True,
        "root": ollama_root(),
        "models": tags.json().get("models", []),
        "running": running.json().get("models", []),
        "active": get_settings().llm.model,
    }


@router.get("/catalog")
async def catalog(q: str = ""):
    items = search_catalog(q) if q else list(CATALOG)
    return {
        "query": q,
        "library_url": "https://ollama.com/library",
        "official_browse_api": False,
        "note": (
            "Ollama’s local API can list, pull, show, and delete models on this PC. "
            "There is no official API to browse ollama.com/library. "
            "ATLAS ships a shortlist of laptop-friendly models; pull any other name from the library."
        ),
        "models": items,
    }


@router.post("/show")
async def show_model(body: ModelName):
    response = await _ollama("POST", "/api/show", json={"model": body.model}, timeout=60.0)
    payload = response.json()
    details = payload.get("details") or {}
    return {
        "model": body.model,
        "modelfile": payload.get("modelfile", ""),
        "parameters": payload.get("parameters", ""),
        "template": payload.get("template", ""),
        "details": details,
        "license": (payload.get("license") or "")[:2000],
    }


@router.post("/pull")
async def pull_model(body: ModelName):
    async def stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{ollama_root()}/api/pull",
                    json={"model": body.model, "stream": True},
                ) as response:
                    if response.status_code >= 400:
                        yield f'{{"status":"error","error":"{response.status_code}"}}\n'
                        return
                    async for line in response.aiter_lines():
                        if line:
                            yield line + "\n"
        except httpx.ConnectError:
            yield '{"status":"error","error":"Ollama is not running"}\n'

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.delete("/model")
async def delete_model(body: ModelName):
    await _ollama("DELETE", "/api/delete", json={"model": body.model})
    return {"deleted": body.model}
