# ATLAS

On-premises assistant for company procedures, departments, and policy. Answers are grounded in internal email (RAG over Qdrant).

**Ollama** runs the chat model. **The default model is Microsoft Phi-3 Mini** (`phi3:latest`) — a small 3.8B model meant for laptops. It is not Google, and it is not a custom ATLAS build. Google’s small model is Gemma (`gemma2:2b`).

## Install on a new Windows PC (no Docker)

You need:

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/) (tick “Add Python to PATH”)
2. **Ollama** — [ollama.com](https://ollama.com) (install, then leave it running in the tray)
3. **Git** — [git-scm.com](https://git-scm.com)

```powershell
git clone https://github.com/ExoFi-Labs/ATLAS.git
cd ATLAS
.\scripts\install.ps1
```

That copies `.env`, installs Python packages, and pulls **Phi-3 Mini** if it is missing.

Then, in the same folder:

```powershell
python -m atlas.cli ingest examples/emails
python -m atlas.cli serve
```

Open **http://localhost:8080**

First ingest downloads the embedding model (`bge-small-en-v1.5`, CPU). After that, ask: *How much PTO do employees accrue?*

### Linux / macOS

```bash
git clone https://github.com/ExoFi-Labs/ATLAS.git
cd ATLAS
chmod +x scripts/install.sh
./scripts/install.sh
python -m atlas.cli ingest examples/emails
python -m atlas.cli serve
```

Docker is **optional** (Qdrant server + vLLM later). This PC uses embedded Qdrant in `data/qdrant/` so Docker is not required.

## Pages in the UI

| Page | What it is |
|------|------------|
| **Chat** | Ask questions. ATLAS searches Qdrant, then answers with the Ollama model. |
| **Qdrant** | Vector database. Upload `.eml` / `.mbox`, browse, open, delete. |
| **Ollama** | Models on this PC. Pull Phi / Llama / Gemma, inspect Modelfiles, switch the chat model. |
| **About** | Live specs and email capacity. |
| **Settings** | Dropdown of installed models, RAG limits, voice. Saves to `.env`. |

## Which model should I run?

| Hardware | Use | Ollama name |
|----------|-----|-------------|
| Work laptop (i7, 8–16 GB RAM, little or no GPU) | **Phi-3 Mini (default)** or Phi-4 Mini | `phi3:latest` / `phi4-mini` |
| Same laptop, want even smaller | Gemma 2 2B (Google) or Llama 3.2 3B | `gemma2:2b` / `llama3.2:3b` |
| Desktop GPU (e.g. 1080 Ti 11 GB) | Llama 3.1 8B for better quality | `llama3.1:8b` |
| Work cluster | vLLM, not Ollama | set `ATLAS_LLM__BASE_URL` |

Phi-3 Mini is about **2.2 GB on disk** and runs on CPU. Expect slower replies on i7-only than on a GPU, but it is usable. 7B–8B models on CPU-only will feel heavy.

Ollama can **list, pull, show, and delete** models on this machine (`/api/tags`, `/api/pull`, …). It does **not** offer an official API to browse [ollama.com/library](https://ollama.com/library). The Ollama page ships a shortlist and lets you pull any library name.

## Add your own email

In the UI: **Qdrant → drop `.eml` or `.mbox` files**.

Or CLI (stop `atlas serve` first if you use embedded Qdrant — only one process can open `data/qdrant`):

```powershell
python -m atlas.cli ingest examples/emails
python -m atlas.cli ingest C:\path\to\export --department hr --roles all-staff,hr
python -m atlas.cli ingest C:\path\to\export --dry-run
```

| Stage | What it does |
|-------|----------------|
| Parse | MIME / HTML / mbox, thread headers |
| Clean | Quoted replies, signatures |
| PII | Regex scrub (`[EMAIL]`, `[PHONE]`, …) |
| Attachments | PDF, Word, Excel, CSV, text extracted into extra chunks |
| Chunk | One vector per message, plus one per attachment |
| Index | Embed with `bge-small` into Qdrant |

Scanned/image PDFs have no text layer — those are skipped until OCR is added. Images (png/jpg) are listed but not read yet.

## Architecture

Swap backends with `.env`. Chat, RAG, and the UI never import Ollama or vLLM directly.

| Piece | Home | Work later |
|-------|------|------------|
| Chat LLM | Ollama + **Phi-3 Mini** | vLLM + larger instruct model |
| Vectors | Qdrant embedded (`data/qdrant`) | Qdrant server |
| Auth | `dev` user | OIDC (Azure AD / Okta) |
| TTS | off, or Google Cloud TTS | same |

```env
ATLAS_LLM__PROVIDER=ollama
ATLAS_LLM__BASE_URL=http://127.0.0.1:11434/v1
ATLAS_LLM__MODEL=phi3:latest
ATLAS_VECTOR__PATH=./data/qdrant
```

Work vLLM example: `deploy/profiles/work.env.example`.

## Configuration

Copy `.env.example` to `.env` (the install script does this).

| Variable | Purpose |
|----------|---------|
| `ATLAS_LLM__MODEL` | Ollama model name (`phi3:latest`) |
| `ATLAS_LLM__BASE_URL` | `http://127.0.0.1:11434/v1` |
| `ATLAS_VECTOR__PATH` | Embedded Qdrant folder. Empty = use `ATLAS_VECTOR__URL` |
| `ATLAS_AUTH__PROVIDER` | `dev` or `oidc` |
| `ATLAS_TTS__PROVIDER` | `none` or `google` |

Do not commit `.env`. Local index lives in `data/` and is gitignored.

## API (selected)

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Process is up |
| `POST /api/chat` | RAG chat |
| `GET /api/sources` | Qdrant email list |
| `GET /api/ollama/status` | Local Ollama models |
| `GET /api/ollama/catalog` | Laptop shortlist |
| `POST /api/ollama/pull` | Download a library model (stream) |

## Roadmap

- [x] Email ingestion, Qdrant console, Ollama model manager
- [ ] OIDC (Azure AD / Okta)
- [ ] Silero VAD + voice UI
- [ ] Hybrid BM25 + reranker

## License

Internal use.
