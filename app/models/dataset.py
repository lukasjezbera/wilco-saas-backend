"""
Dataset Model
Uploaded CSV/Excel files per tenant
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.session import Base


class Dataset(Base):
    """
    Dataset model - uploaded data files
    
    Each tenant can upload multiple datasets (Sales.csv, Documents.csv, etc.)
    Files are stored with metadata about columns, rows, etc.
    """
    
    __tablename__ = "datasets"
    
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
        index=True,
        comment="Tenant that owns this dataset"
    )
    
    filename = Column(
        String(255),
        nullable=False,
        comment="Internal filename (e.g., 'sales_uuid.csv')"
    )
    
    original_filename = Column(
        String(255),
        nullable=False,
        comment="Original uploaded filename (e.g., 'Sales.csv')"
    )
    
    file_path = Column(
        Text,
        nullable=False,
        comment="Path to stored file"
    )
    
    file_hash = Column(
        String(64),
        nullable=True,
        comment="SHA256 hash for deduplication"
    )
    
    file_size_bytes = Column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )
    
    rows = Column(
        Integer,
        nullable=True,
        comment="Number of rows in dataset"
    )
    
    columns = Column(
        JSONB,
        nullable=True,
        comment="Column names and types: {\"col1\": \"int64\", \"col2\": \"object\"}"
    )
    
    dataset_metadata = Column(
        JSONB,
        nullable=True,
        comment="Additional metadata (date range, categories, etc.)"
    )
    
    uploaded_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    uploaded_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who uploaded this dataset"
    )
    
    last_used_at = Column(
        DateTime,
        nullable=True,
        comment="Last time this dataset was queried"
    )
    
    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    
    tenant = relationship(
        "Tenant",
        back_populates="datasets"
    )
    
    uploader = relationship(
        "User",
        foreign_keys=[uploaded_by],
        back_populates="uploaded_datasets"
    )
    
    # ==========================================
    # METHODS
    # ==========================================
    
    def __repr__(self):
        return f"<Dataset(id={self.id}, filename='{self.original_filename}')>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size_mb": round(self.file_size_bytes / (1024 * 1024), 2) if self.file_size_bytes else None,
            "rows": self.rows,
            "columns": self.columns,
            "metadata": self.metadata,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "uploaded_by": str(self.uploaded_by) if self.uploaded_by else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None
        }
