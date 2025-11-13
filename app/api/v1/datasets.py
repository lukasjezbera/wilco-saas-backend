"""
Dataset API Endpoints
Upload, list, delete datasets
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import pandas as pd
import hashlib
import os
import shutil
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.dataset import Dataset
from app.api.v1.auth import get_current_user
from app.core.config import settings


router = APIRouter(prefix="/datasets", tags=["Datasets"])


# ==========================================
# UPLOAD DATASET
# ==========================================

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload CSV or Excel file
    
    - Validates file type and size
    - Stores file with metadata
    - Returns dataset ID
    """
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ['.csv', '.xlsx', '.xls']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: .csv, .xlsx, .xls"
        )
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size (max 100MB)
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE / (1024*1024)}MB"
        )
    
    # Calculate file hash
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Check for duplicates
    existing = db.query(Dataset).filter(
        Dataset.tenant_id == current_user.tenant_id,
        Dataset.file_hash == file_hash
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File already exists: {existing.original_filename}"
        )
    
    # Create upload directory
    upload_dir = f"/tmp/wilco-datasets/{current_user.tenant_id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    import uuid
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Read dataset metadata
    try:
        if file_ext == '.csv':
            df = pd.read_csv(file_path, nrows=5)  # Just peek
        else:
            df = pd.read_excel(file_path, nrows=5)
        
        # Get full row count
        if file_ext == '.csv':
            row_count = sum(1 for _ in open(file_path)) - 1  # Subtract header
        else:
            row_count = len(pd.read_excel(file_path))
        
        columns_info = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
    except Exception as e:
        # Clean up file if reading fails
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )
    
    # Create dataset record
    dataset = Dataset(
        tenant_id=current_user.tenant_id,
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_hash=file_hash,
        file_size_bytes=file_size,
        rows=row_count,
        columns=columns_info,
        uploaded_by=current_user.id
    )
    
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    
    return {
        "id": str(dataset.id),
        "filename": dataset.original_filename,
        "size_mb": round(file_size / (1024 * 1024), 2),
        "rows": row_count,
        "columns": list(columns_info.keys()),
        "uploaded_at": dataset.uploaded_at.isoformat()
    }


# ==========================================
# LIST DATASETS
# ==========================================

@router.get("/")
def list_datasets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all datasets for current tenant"""
    
    datasets = db.query(Dataset).filter(
        Dataset.tenant_id == current_user.tenant_id
    ).order_by(Dataset.uploaded_at.desc()).all()
    
    return {
        "total": len(datasets),
        "datasets": [
            {
                "id": str(d.id),
                "filename": d.original_filename,
                "size_mb": round(d.file_size_bytes / (1024 * 1024), 2),
                "rows": d.rows,
                "columns": list(d.columns.keys()) if d.columns else [],
                "uploaded_at": d.uploaded_at.isoformat()
            }
            for d in datasets
        ]
    }


# ==========================================
# DELETE DATASET
# ==========================================

@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete dataset"""
    
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.tenant_id == current_user.tenant_id
    ).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Delete file
    try:
        if os.path.exists(dataset.file_path):
            os.remove(dataset.file_path)
    except Exception as e:
        print(f"Warning: Could not delete file {dataset.file_path}: {e}")
    
    # Delete DB record
    db.delete(dataset)
    db.commit()
    
    return {"message": f"Dataset '{dataset.original_filename}' deleted"}