import os
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.knowledge_base.embeddings import (
    get_embedding_provider,
    get_hash_provider,
    DeterministicHashEmbeddingProvider,
)
from app.knowledge_base.vector_store import search_similar_chunks
from app.db.session import SessionLocal

client = TestClient(app)


def test_default_embedding_provider_is_lightweight_hash():
    """Verify get_embedding_provider defaults to DeterministicHashEmbeddingProvider (<1MB RAM)."""
    provider = get_embedding_provider()
    assert isinstance(provider, DeterministicHashEmbeddingProvider)
    assert provider.dimension == 384


def test_mock_llm_provider_defaults_to_hash_embeddings(monkeypatch):
    """Verify that when LLM_PROVIDER=mock, get_embedding_provider always returns the lightweight hash provider."""
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    provider = get_embedding_provider()
    assert isinstance(provider, DeterministicHashEmbeddingProvider)


def test_hash_embedding_provider_singleton_caching():
    """Verify that get_hash_provider reuses the cached instance to prevent memory bloat."""
    p1 = get_hash_provider()
    p2 = get_hash_provider()
    assert p1 is p2


def test_database_pool_settings_configured_for_low_memory():
    """Verify settings are tuned for low-memory container environments (e.g., Render 512MB)."""
    assert settings.DB_POOL_SIZE <= 5
    assert settings.DB_MAX_OVERFLOW <= 5
    assert settings.EMBEDDING_PROVIDER == "hash"


def test_cors_registration_for_vercel_production_origin():
    """Verify deployed FastAPI application registers CORS middleware correctly for Vercel production frontend."""
    resp = client.get("/health", headers={"Origin": "https://lenny-growth-assistant-ai.vercel.app"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://lenny-growth-assistant-ai.vercel.app"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_for_conversations():
    """Verify OPTIONS preflight request from Vercel receives appropriate CORS headers."""
    resp = client.options(
        "/api/conversations",
        headers={
            "Origin": "https://lenny-growth-assistant-ai.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://lenny-growth-assistant-ai.vercel.app"
