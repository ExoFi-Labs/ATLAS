from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseModel):
    provider: Literal["dev", "oidc"] = "dev"
    dev_user_id: str = "dev-user"
    dev_roles: str = "all-staff,admin"
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""


class LLMSettings(BaseModel):
    provider: Literal["ollama", "vllm", "openai_compat"] = "ollama"
    base_url: str = "http://localhost:11434/v1"
    model: str = "phi3:latest"
    api_key: str = "ollama"
    max_tokens: int = 1024
    temperature: float = 0.2


class EmbeddingsSettings(BaseModel):
    provider: Literal["sentence_transformers"] = "sentence_transformers"
    model: str = "BAAI/bge-small-en-v1.5"
    device: str = "cpu"


class VectorSettings(BaseModel):
    provider: Literal["qdrant"] = "qdrant"
    url: str = "http://localhost:6333"
    path: str = ""  # if set, use embedded Qdrant on disk (no Docker / no server)
    collection: str = "atlas_email_chunks"


class RAGSettings(BaseModel):
    top_k: int = 20
    top_n: int = 5
    min_score: float = 0.35


class TTSSettings(BaseModel):
    provider: Literal["google", "none"] = "google"
    google_voice: str = "en-US-Neural2-J"
    google_language: str = "en-US"
    google_credentials_file: str = ""


class STTSettings(BaseModel):
    provider: Literal["whisper", "none"] = "whisper"
    whisper_model: str = "base"
    whisper_device: str = "cpu"


class IngestionSettings(BaseModel):
    default_roles: str = "all-staff"
    default_department: str = "general"
    max_chunk_tokens: int = 1200


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://atlas:atlas@localhost:5432/atlas"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ATLAS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    env: Literal["development", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    cors_origins: str = "http://localhost:8080"

    auth: AuthSettings = Field(default_factory=AuthSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    embeddings: EmbeddingsSettings = Field(default_factory=EmbeddingsSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    tts: TTSSettings = Field(default_factory=TTSSettings)
    stt: STTSettings = Field(default_factory=STTSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
