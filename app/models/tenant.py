"""
Tenant Model
Multi-tenant architecture - každá firma = tenant
"""

from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.session import Base


class Tenant(Base):
    """
    Tenant (Company) model
    
    Každý tenant reprezentuje jednu firmu/organizaci.
    Všechna data jsou izolovaná per tenant.
    """
    
    __tablename__ = "tenants"
    
    # ==========================================
    # COLUMNS
    # ==========================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    name = Column(
        String(255),
        nullable=False,
        comment="Company/organization name"
    )
    
    subdomain = Column(
        String(100),
        unique=True,
        nullable=True,
        comment="Optional custom subdomain (e.g., 'alza' -> alza.wilco.cz)"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        comment="Tenant is active and can access platform"
    )
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    
    users = relationship(
        "User",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    datasets = relationship(
        "Dataset",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    queries = relationship(
        "QueryHistory",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    settings = relationship(
        "TenantSettings",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    # ==========================================
    # METHODS
    # ==========================================
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}')>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "subdomain": self.subdomain,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
