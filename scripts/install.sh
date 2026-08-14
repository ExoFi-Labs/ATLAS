#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> ATLAS install (no Docker required)"

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Python 3.10+ is required."
  exit 1
fi
PYTHON_BIN="$(command -v python3 || command -v python)"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is required. Install from https://ollama.com then re-run."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env (chat model: Microsoft Phi-3 Mini / phi3:latest)"
fi

echo "==> Installing Python package"
"$PYTHON_BIN" -m pip install -e .

echo "==> Ensuring Phi-3 Mini is available"
ollama pull phi3:latest

cat <<'EOF'

ATLAS is installed.

Next:
  python -m atlas.cli ingest examples/emails
  python -m atlas.cli serve

Open http://localhost:8080
Default chat model: Microsoft Phi-3 Mini (phi3:latest) via Ollama — not Google.

EOF
