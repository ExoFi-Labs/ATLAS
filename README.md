# ATLAS

On-premises, modular RAG assistant for company procedures, departments, and policy — grounded on internal email.

Designed for **home development now** and **work deployment later** without rewriting application code. Swap backends via environment variables only.

## Quick install (home)

**Requirements:** Docker Desktop, [Ollama](https://ollama.com)

```powershell
git clone https://github.com/YOUR_ORG/ATLAS.git
cd ATLAS
.\scripts\install.ps1
ollama pull llama3.1:8b
```

Open http://localhost:8080

Index the sample policy emails (first run downloads the embedding model):

```powershell
docker compose exec atlas atlas ingest examples/emails
```

Then ask: *How much PTO do employees accrue?* or *Who owns expense reports?*

Linux/macOS:

```bash
git clone https://github.com/YOUR_ORG/ATLAS.git
cd ATLAS
./scripts/install.sh
ollama pull llama3.1:8b
docker compose exec atlas atlas ingest examples/emails
```

## Email ingestion

Drop `.eml` or `.mbox` files into a folder and index them. The pipeline is modular: parse → reconstruct threads → strip quotes/signatures → scrub PII → message-level chunks → embed → Qdrant.

```powershell
# Inside the API container (uses ATLAS_VECTOR__URL=http://qdrant:6333)
docker compose exec atlas atlas ingest examples/emails

# Preview only — no embeddings or Qdrant writes
docker compose exec atlas atlas ingest examples/emails --dry-run

# Tag a department and restrict retrieval roles
docker compose exec atlas atlas ingest examples/emails --department hr --roles all-staff,hr
```

From the host (point Qdrant at the published port):

```powershell
$env:ATLAS_VECTOR__URL="http://localhost:6333"
atlas ingest examples/emails
```

Chunks are idempotent (stable IDs from `Message-ID`). Re-running ingest updates the same points.

| Stage | What it does |
|-------|----------------|
| Parse | MIME / HTML / mbox, headers, `In-Reply-To` / `References` |
| Clean | Quoted-reply stripping, signature/footer removal |
| PII | Regex scrubber (`RegexPIIScrubber`) — swap for Presidio later |
| Chunk | One chunk per message (split long bodies on paragraphs) |
| Index | Embed with `bge-small` and upsert to Qdrant with `allowed_roles` |

## Modular architecture

Every external system sits behind a **provider interface**. The API, RAG pipeline, and UI never import Ollama, vLLM, or Google directly — they use `ProviderRegistry`.

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│  web/ UI    │────▶│  atlas/api       │────▶│  atlas/rag/pipeline     │
└─────────────┘     └────────┬─────────┘     └───────────┬─────────────┘
                             │                             │
                    ┌────────▼─────────┐          ┌────────▼─────────┐
                    │ ProviderRegistry │          │ Vector + Embed   │
                    └────────┬─────────┘          └──────────────────┘
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    LLM (Ollama/vLLM)   Auth (dev/OIDC)    TTS (Google/none)
```

| Component | Interface | Home default | Work swap |
|-----------|-----------|--------------|-----------|
| LLM | `LLMProvider` | Ollama (`ATLAS_LLM__BASE_URL`) | vLLM — change URL only |
| Auth | `AuthProvider` | `dev` | `oidc` (Azure AD / Okta) |
| Vector DB | `VectorStoreProvider` | Qdrant | same |
| Embeddings | `EmbeddingsProvider` | sentence-transformers (CPU) | optional CUDA |
| TTS | `TTSProvider` | Google Cloud TTS | same |
| STT | `STTProvider` | faster-whisper | same |

### Swap example: Ollama → vLLM

Only `.env` changes — no code changes:

```env
ATLAS_LLM__PROVIDER=vllm
ATLAS_LLM__BASE_URL=http://vllm:8000/v1
ATLAS_LLM__MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct-AWQ
```

Then enable the vLLM service:

```bash
docker compose --profile vllm up -d
```

See `deploy/profiles/home.env.example` and `deploy/profiles/work.env.example`.

### Swap example: dev auth → SSO

```env
ATLAS_AUTH__PROVIDER=oidc
ATLAS_AUTH__OIDC_ISSUER=https://login.microsoftonline.com/{tenant}/v2.0
ATLAS_AUTH__OIDC_CLIENT_ID=...
ATLAS_AUTH__OIDC_CLIENT_SECRET=...
```

Implement token validation in `src/atlas/providers/auth/oidc.py` — the rest of ATLAS already filters retrieval by `UserContext.roles`.

## Work migration checklist

1. Clone repo on server: `git clone ... && cp deploy/profiles/work.env.example .env`
2. Fill in OIDC secrets and Google TTS credentials
3. `docker compose up -d` (+ `--profile vllm` if using bundled vLLM)
4. Point LLM at your inference cluster (`ATLAS_LLM__BASE_URL`)
5. Run `atlas ingest /path/to/mail-export` against the production mailbox dump
6. Verify RBAC filters with real SSO group → role mappings

**You do not start over.** Same repo, same UI, same RAG code — different `.env`.

## Configuration

Copy `.env.example` to `.env`. All settings use the `ATLAS_` prefix with nested `__` segments:

| Variable | Purpose |
|----------|---------|
| `ATLAS_LLM__BASE_URL` | OpenAI-compatible LLM endpoint |
| `ATLAS_LLM__MODEL` | Model name |
| `ATLAS_AUTH__PROVIDER` | `dev` or `oidc` |
| `ATLAS_AUTH__DEV_ROLES` | Comma-separated roles for local RBAC testing |
| `ATLAS_VECTOR__URL` | Qdrant URL |
| `ATLAS_INGESTION__DEFAULT_ROLES` | ACL roles written onto ingested chunks |
| `ATLAS_TTS__PROVIDER` | `google` or `none` |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP service account for TTS |

## Local development (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
copy .env.example .env
atlas serve
```

Ingest from the host after Qdrant is up:

```powershell
$env:ATLAS_VECTOR__URL="http://localhost:6333"
atlas ingest examples/emails
```

Run Qdrant separately (`docker compose up qdrant postgres -d`) or adjust URLs to localhost.

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Status + active providers |
| `POST /api/chat` | RAG chat (JSON) |
| `POST /api/chat/stream` | SSE streaming |
| `POST /api/voice/transcribe` | Upload audio → text |
| `POST /api/voice/synthesize` | Text → MP3 (Google TTS) |

## Project layout

```
ATLAS/
├── src/atlas/
│   ├── api/              # FastAPI gateway
│   ├── config.py         # All env-driven settings
│   ├── providers/        # Swappable backends
│   │   ├── registry.py   # Factory — single swap point
│   │   ├── llm/          # OpenAI-compatible (Ollama + vLLM)
│   │   ├── auth/         # dev + OIDC stub
│   │   ├── vector/       # Qdrant
│   │   ├── tts/          # Google
│   │   └── stt/          # Whisper
│   ├── rag/              # Retrieval + prompt assembly
│   └── ingestion/        # Email parse, PII, chunk, index
├── examples/emails/      # Sample policy threads for local RAG
├── web/                  # Minimal chat UI
├── deploy/profiles/      # home vs work env templates
├── docker-compose.yml
└── scripts/install.ps1   # One-command setup
```

## Roadmap

- [x] Email ingestion pipeline (thread parse, PII scrub, chunk, index)
- [ ] OIDC implementation (Azure AD / Okta)
- [ ] Silero VAD in browser + voice mode UI
- [ ] Hybrid BM25 + reranker

## License

Internal use — adjust as needed.
