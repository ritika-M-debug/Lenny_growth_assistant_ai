from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.conversations import router as conversations_router
from app.api.artifacts import router as artifacts_router

api_router = APIRouter()

# Health endpoints (/health, /health/db)
api_router.include_router(health_router)

# Conversation endpoints (/api/conversations)
api_router.include_router(conversations_router, prefix="/api")

# Artifact endpoints (/api/conversations/{id}/artifacts, /api/artifacts/{id})
api_router.include_router(artifacts_router, prefix="/api")
