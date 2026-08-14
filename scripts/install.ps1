$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> ATLAS install"

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "Docker is required. Install Docker Desktop and re-run scripts/install.ps1"
  exit 1
}

Write-Host "==> Starting infrastructure (Qdrant, Postgres, ATLAS API)"
docker compose up -d --build

Write-Host @"

ATLAS is starting.

Next steps:
1. Install Ollama:  https://ollama.com
2. Pull a model:    ollama pull llama3.1:8b
5. Index sample emails:
   docker compose exec atlas atlas ingest examples/emails
6. Open the UI and ask: "How much PTO do employees accrue?"

Work migration:
- Copy deploy/profiles/work.env.example values into .env
- Enable vLLM:      docker compose --profile vllm up -d
- Switch auth:      ATLAS_AUTH__PROVIDER=oidc

"@
