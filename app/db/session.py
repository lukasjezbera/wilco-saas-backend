"""
Database Base Configuration
SQLAlchemy setup with UUID support
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.core.config import settings


# ==========================================
# DATABASE ENGINE
# ==========================================

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ==========================================
# DATABASE DEPENDENCY
# ==========================================

def get_db():
    """
    Database session dependency for FastAPI
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# UUID HELPER
# ==========================================

def generate_uuid() -> str:
    """Generate UUID4 as string"""
    return str(uuid.uuid4())


# ==========================================
# EXPORT
# ==========================================

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "generate_uuid"
]
