$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> ATLAS install (Windows, no Docker required)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "Python 3.10+ is required. Install from https://www.python.org/downloads/ (Add to PATH)."
  exit 1
}

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Write-Host "Ollama is required. Install from https://ollama.com then re-run this script."
  exit 1
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example (chat model: Microsoft Phi-3 Mini / phi3:latest)"
}

Write-Host "==> Installing Python package"
python -m pip install -e .

Write-Host "==> Ensuring Phi-3 Mini is available (small laptop model, ~2.2 GB)"
ollama pull phi3:latest

Write-Host @"

ATLAS is installed.

Next:
  python -m atlas.cli ingest examples/emails
  python -m atlas.cli serve

Then open http://localhost:8080
  Chat    — ask policy questions
  Qdrant  — upload / browse email vectors
  Ollama  — list, pull, and switch models (Phi, Llama, Gemma, …)

Default chat model: Microsoft Phi-3 Mini (phi3:latest) via Ollama.
That is not Google. Gemma is Google's small model if you want it.

"@
