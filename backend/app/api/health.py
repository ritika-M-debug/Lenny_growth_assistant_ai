import os
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.db.session import check_db_connection, get_db
from app.core.config import settings
from app.agents.rag_agent import get_default_llm_provider
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.knowledge_base.embeddings import get_embedding_provider
from app.db.init_db import seed_transcripts_if_empty

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


@router.get("/health/rag", tags=["Health"])
async def health_rag_check(db: Session = Depends(get_db)):
    """
    Diagnostic endpoint to inspect RAG Knowledge Base readiness,
    document counts, chunk counts, and embedding provider configuration.
    """
    try:
        doc_count = db.query(KnowledgeDocument).count()
        chunk_count = db.query(KnowledgeChunk).count()
        emb_provider = get_embedding_provider()
        return {
            "status": "ready" if chunk_count > 0 else "empty",
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "embedding_provider": type(emb_provider).__name__,
            "embedding_dimension": emb_provider.dimension,
            "message": "Knowledge base populated with genuine transcripts." if chunk_count > 0 else "Knowledge base is empty."
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Failed to inspect RAG knowledge base."
        }


@router.post("/health/rag/seed", tags=["Health"])
async def trigger_rag_seed(db: Session = Depends(get_db)):
    """
    On-demand endpoint to seed or verify transcript ingestion into PostgreSQL.
    Idempotent: skips already-ingested transcripts.
    """
    try:
        seeded_count = seed_transcripts_if_empty(session=db)
        doc_count = db.query(KnowledgeDocument).count()
        chunk_count = db.query(KnowledgeChunk).count()
        return {
            "status": "success",
            "seeded_count": seeded_count,
            "document_count": doc_count,
            "chunk_count": chunk_count,
            "message": f"Knowledge base ready ({doc_count} documents, {chunk_count} chunks)."
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed knowledge base: {e}"
        )
