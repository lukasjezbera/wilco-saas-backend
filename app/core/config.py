"""
Core Configuration
Centralized settings using Pydantic BaseSettings
"""

from pydantic_settings import BaseSettings
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # ==========================================
    # APPLICATION
    # ==========================================
    APP_NAME: str = "Wilco SaaS API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # ==========================================
    # DATABASE
    # ==========================================
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # ==========================================
    # SECURITY
    # ==========================================
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # ==========================================
    # ANTHROPIC API
    # ==========================================
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    ANTHROPIC_MAX_TOKENS: int = 2000
    
    # ==========================================
    # OPENAI API (for Speech-to-Text)
    # ==========================================
    OPENAI_API_KEY: str = ""
    OPENAI_WHISPER_MODEL: str = "whisper-1"
    
    # ==========================================
    # CORS
    # ==========================================
    BACKEND_CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://app.wilco.cz",
        "https://wilco.cz",
        "https://wilco-saas-frontend.vercel.app",
        # Vercel preview deployments
        "https://wilco-saas-frontend-git-main-lukass-projects-d04dcf3d.vercel.app",
        "https://wilco-saas-frontend-lukass-projects-d04dcf3d.vercel.app",
    ]
    
    # ==========================================
    # FILE UPLOAD
    # ==========================================
    MAX_UPLOAD_SIZE: int = 200 * 1024 * 1024  # 200MB
    ALLOWED_EXTENSIONS: set = {".csv", ".xlsx", ".xls"}
    UPLOAD_DIR: str = "data/uploads"
    
    # ==========================================
    # QUERY SETTINGS
    # ==========================================
    MAX_QUERY_EXECUTION_TIME: int = 120  # seconds
    MAX_RESULT_ROWS: int = 100000
    QUERY_CACHE_TTL: int = 3600  # 1 hour
    
    # ==========================================
    # RATE LIMITING
    # ==========================================
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# ==========================================
# SINGLETON INSTANCE
# ==========================================

settings = Settings()


# ==========================================
# DERIVED SETTINGS
# ==========================================

def get_database_url() -> str:
    """Get formatted database URL"""
    return settings.DATABASE_URL


def is_production() -> bool:
    """Check if running in production"""
    return settings.ENVIRONMENT.lower() == "production"


def is_development() -> bool:
    """Check if running in development"""
    return settings.ENVIRONMENT.lower() == "development"


# ==========================================
# EXPORT
# ==========================================

__all__ = [
    "settings",
    "Settings",
    "get_database_url",
    "is_production",
    "is_development"
]
