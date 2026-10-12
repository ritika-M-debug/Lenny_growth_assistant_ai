import os
from fastapi import APIRouter, HTTPException, status
from app.db.session import check_db_connection
from app.core.config import settings
from app.agents.rag_agent import get_default_llm_provider

router = APIRouter()


@router.get("/health", tags=["Health"])
async def health_check():
    """
    Main application health check endpoint.
    Reports operational status and current active provider configuration.
    Never fails due to optional external cloud services.
    """
    active_provider = (os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER or "ollama").lower()
    active_model = settings.OLLAMA_MODEL if active_provider == "ollama" else settings.effective_anthropic_model

    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "llm_provider": active_provider,
        "model": active_model
    }


@router.get("/health/db", tags=["Health"])
async def health_db_check():
    """
    Database readiness endpoint to verify PostgreSQL reachability.
    Executes a simple 'SELECT 1' query without exposing any sensitive credentials.
    """
    is_healthy, message = check_db_connection()
    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "message": message
            }
        )
    return {
        "status": "healthy",
        "database": "connected",
        "database_name": settings.POSTGRES_DB,
        "message": message
    }


@router.get("/health/llm", tags=["Health"])
async def health_llm_check():
    """
    Diagnostic endpoint to inspect the active LLM provider's reachability,
    model installation, and configuration status.
    Does NOT fail the service with 5xx; returns diagnostic report for observability.
    """
    active_provider_name = (os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER or "ollama").lower()

    try:
        # Use active provider (do not force mock unless configured)
        provider = get_default_llm_provider(allow_mock_override=False)
        diagnostics = provider.check_health()
        return {
            "status": diagnostics.get("status", "unknown"),
            "provider": provider.provider_name,
            "model": provider.model_name,
            "diagnostics": diagnostics
        }
    except Exception as e:
        return {
            "status": "misconfigured",
            "provider": active_provider_name,
            "error": str(e),
            "diagnostics": {
                "message": f"Failed to initialize or inspect provider '{active_provider_name}': {e}"
            }
        }
