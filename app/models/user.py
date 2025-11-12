"""
User Model
User authentication and authorization
"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.session import Base


class User(Base):
    """
    User model with multi-tenant support
    
    Each user belongs to exactly one tenant.
    """
    
    __tablename__ = "users"
    
    # ==========================================
    # COLUMNS
    # ==========================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        comment="Tenant this user belongs to"
    )
    
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email (login identifier)"
    )
    
    hashed_password = Column(
        String(255),
        nullable=False,
        comment="Bcrypt hashed password"
    )
    
    full_name = Column(
        String(255),
        nullable=True,
        comment="User's full name"
    )
    
    is_active = Column(
        Boolean,
        default=True,
        comment="User can login and access system"
    )
    
    is_superuser = Column(
        Boolean,
        default=False,
        comment="User has admin privileges"
    )
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    last_login = Column(
        DateTime,
        nullable=True,
        comment="Last successful login timestamp"
    )
    
    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    
    tenant = relationship(
        "Tenant",
        back_populates="users"
    )
    
    queries = relationship(
        "QueryHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    uploaded_datasets = relationship(
        "Dataset",
        foreign_keys="Dataset.uploaded_by",
        back_populates="uploader"
    )
    
    # ==========================================
    # METHODS
    # ==========================================
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
    
    def to_dict(self, include_tenant=False):
        """Convert to dictionary"""
        data = {
            "id": str(self.id),
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }
        
        if include_tenant and self.tenant:
            data["tenant"] = self.tenant.to_dict()
        
        return data
