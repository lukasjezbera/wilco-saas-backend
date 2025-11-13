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

@router.get("/test-claude")
async def test_claude():
    """Test Claude API directly"""
    try:
        from app.core.claude_service import ClaudeService
        from app.core.config import settings
        
        claude = ClaudeService(api_key=settings.ANTHROPIC_API_KEY)
        
        result = claude.generate_python_code(
            prompt="Generate Python code that calculates 2 + 2 and stores it in a variable called 'result'",
            max_tokens=100
        )
        
        return {
            "success": True,
            "generated_code": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }