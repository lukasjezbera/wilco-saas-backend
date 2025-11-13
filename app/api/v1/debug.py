from fastapi import APIRouter
from app.core.config import settings

router = APIRouter(prefix="/debug", tags=["Debug"])

@router.get("/config")
def get_config():
    """Debug endpoint - show config"""
    return {
        "anthropic_api_key_length": len(settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else 0,
        "anthropic_api_key_start": settings.ANTHROPIC_API_KEY[:20] if settings.ANTHROPIC_API_KEY else "EMPTY",
        "anthropic_model": settings.ANTHROPIC_MODEL,
        "environment": settings.ENVIRONMENT
    }