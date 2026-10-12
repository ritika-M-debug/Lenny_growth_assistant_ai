import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router
from app.db.init_db import init_db

logger = logging.getLogger("lenny_assistant.main")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Backend API for The Lenny Growth Assistant - Conversational AI for Product & Growth"
)

# Setup CORS middleware allowing Vercel production frontend and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """
    Ensures database tables are safely created on app startup if reachable,
    and validates configured LLM provider settings with actionable warnings.
    """
    try:
        init_db()
    except Exception as e:
        logger.warning("Startup DB init notice: %s", e)

    # Validate active LLM provider configuration at startup
    active_provider = (os.getenv("LLM_PROVIDER") or settings.LLM_PROVIDER or "ollama").strip().lower()
    valid_providers = {"ollama", "anthropic", "claude-agent-sdk", "claude_agent_sdk", "claude", "mock"}
    if active_provider not in valid_providers:
        logger.error(
            "Unsupported LLM_PROVIDER '%s'. Supported options are: 'ollama', 'anthropic', 'claude-agent-sdk', 'mock'.",
            active_provider
        )
    elif active_provider in {"anthropic", "claude", "claude-agent-sdk", "claude_agent_sdk"}:
        key = os.getenv("ANTHROPIC_API_KEY") or settings.ANTHROPIC_API_KEY or ""
        if not key or key.startswith("your_") or key == "placeholder":
            logger.warning(
                "LLM_PROVIDER is set to '%s' but ANTHROPIC_API_KEY is not configured. "
                "Cloud requests will fail until an API key is provided in backend/.env. "
                "Set LLM_PROVIDER=ollama for local inference.",
                active_provider
            )
    else:
        logger.info("Active LLM provider configured: '%s'", active_provider)

# Include API Router (includes /health, /health/db, /health/llm, /api/conversations, /api/artifacts)
app.include_router(api_router)

@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint delivering basic application information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "description": "Welcome to The Lenny Growth Assistant API."
    }
