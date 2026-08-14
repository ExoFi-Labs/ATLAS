#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> ATLAS install"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — review before production use."
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker and re-run scripts/install.sh"
  exit 1
fi

echo "==> Starting infrastructure (Qdrant, Postgres, ATLAS API)"
docker compose up -d --build

cat <<'EOF'

ATLAS is starting.

Next steps:
1. Install Ollama locally: https://ollama.com
2. Pull a model:         ollama pull llama3.1:8b
3. Open the UI:          http://localhost:8080
4. Health check:         http://localhost:8080/api/health
5. Index sample emails:
   docker compose exec atlas atlas ingest examples/emails
6. Ask in the UI:        "How much PTO do employees accrue?"

Work migration:
- Copy deploy/profiles/work.env.example values into .env
- Enable vLLM profile: docker compose --profile vllm up -d
- Switch auth:         ATLAS_AUTH__PROVIDER=oidc

EOF
