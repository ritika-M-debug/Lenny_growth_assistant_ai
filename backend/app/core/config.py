import os
from urllib.parse import quote_plus
from pydantic import ConfigDict, computed_field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "The Lenny Growth Assistant"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "lenny_growth_db"
    DATABASE_URL: str | None = None

    @computed_field
    @property
    def sync_database_url(self) -> str:
        # Use individual parameters with URL-encoded password if provided
        if self.POSTGRES_USER and self.POSTGRES_PASSWORD and self.POSTGRES_DB:
            pwd = quote_plus(self.POSTGRES_PASSWORD)
            server = "127.0.0.1" if self.POSTGRES_SERVER in ["localhost", "::1"] else self.POSTGRES_SERVER
            return f"postgresql+psycopg2://{self.POSTGRES_USER}:{pwd}@{server}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        
        if self.DATABASE_URL and self.DATABASE_URL.strip():
            url = self.DATABASE_URL.strip()
            if "@localhost" in url:
                url = url.replace("@localhost", "@127.0.0.1")
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            return url
            
        return f"postgresql+psycopg2://{self.POSTGRES_USER}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # CORS Allowed Origins (Comma-separated string or list supported)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175"

    @computed_field
    @property
    def cors_origins(self) -> list[str]:
        if not self.ALLOWED_ORIGINS:
            return ["*"]
        if isinstance(self.ALLOWED_ORIGINS, list):
            return self.ALLOWED_ORIGINS
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # LLM Settings & Provider Configuration
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT: float = 60.0
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_TIMEOUT: float = 60.0
    ANTHROPIC_MAX_RETRIES: int = 2
    OPENAI_API_KEY: str = ""
    DEFAULT_CLOUD_MODEL: str = "claude-3-5-sonnet-20241022"
    LLM_FALLBACK_PROVIDER: str | None = None

    @computed_field
    @property
    def effective_anthropic_model(self) -> str:
        return self.ANTHROPIC_MODEL or self.DEFAULT_CLOUD_MODEL or "claude-3-5-sonnet-20241022"

    # RAG Retrieval Settings
    RAG_TOP_K: int = 5
    RAG_MIN_SIMILARITY: float = 0.0

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
