from __future__ import annotations

from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

WRITABLE = {
    "ATLAS_LLM__MODEL",
    "ATLAS_LLM__BASE_URL",
    "ATLAS_LLM__MAX_TOKENS",
    "ATLAS_LLM__TEMPERATURE",
    "ATLAS_RAG__TOP_K",
    "ATLAS_RAG__TOP_N",
    "ATLAS_RAG__MIN_SCORE",
    "ATLAS_TTS__PROVIDER",
    "ATLAS_TTS__GOOGLE_VOICE",
    "ATLAS_TTS__SPEAKING_RATE",
    "ATLAS_STT__PROVIDER",
    "ATLAS_STT__WHISPER_MODEL",
    "ATLAS_STT__VAD",
    "ATLAS_STT__VAD_THRESHOLD",
    "ATLAS_STT__VAD_MIN_SILENCE_MS",
    "ATLAS_INGESTION__DEFAULT_ROLES",
    "ATLAS_INGESTION__DEFAULT_DEPARTMENT",
    "ATLAS_AUTH__DEV_ROLES",
}


def update_env_file(updates: dict[str, str], path: Path | None = None) -> list[str]:
    env_path = path or ENV_PATH
    if not env_path.exists():
        raise FileNotFoundError(str(env_path))

    allowed = {key: str(value) for key, value in updates.items() if key in WRITABLE}
    lines = env_path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    written: list[str] = []
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in allowed:
            new_lines.append(f"{key}={allowed[key]}")
            seen.add(key)
            written.append(key)
        else:
            new_lines.append(line)
    for key, value in allowed.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")
            written.append(key)
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return written
