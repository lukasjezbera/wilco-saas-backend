"""
Dataset API Endpoints
Upload, list, delete, preview datasets
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
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
    
    # Validate file size (max 200MB)
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
            # Try European format first (semicolon delimiter, comma decimal)
            try:
                df = pd.read_csv(
                    file_path, 
                    nrows=5, 
                    sep=';', 
                    decimal=',', 
                    encoding='utf-8'
                )
            except:
                # Fallback to standard CSV format (comma delimiter, dot decimal)
                df = pd.read_csv(
                    file_path, 
                    nrows=5, 
                    encoding='utf-8'
                )
        else:
            df = pd.read_excel(file_path, nrows=5)
        
        # Get full row count
        if file_ext == '.csv':
            row_count = sum(1 for _ in open(file_path, encoding='utf-8')) - 1  # Subtract header
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
                "column_types": d.columns if d.columns else {},
                "uploaded_at": d.uploaded_at.isoformat(),
                "last_used_at": d.last_used_at.isoformat() if d.last_used_at else None
            }
            for d in datasets
        ]
    }


# ==========================================
# GET DATASET DETAIL
# ==========================================

@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get dataset details by ID"""
    
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.tenant_id == current_user.tenant_id
    ).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    return {
        "id": str(dataset.id),
        "filename": dataset.original_filename,
        "size_mb": round(dataset.file_size_bytes / (1024 * 1024), 2),
        "rows": dataset.rows,
        "columns": list(dataset.columns.keys()) if dataset.columns else [],
        "column_types": dataset.columns if dataset.columns else {},
        "uploaded_at": dataset.uploaded_at.isoformat(),
        "last_used_at": dataset.last_used_at.isoformat() if dataset.last_used_at else None
    }


# ==========================================
# 🆕 DATASET PREVIEW - First N rows
# ==========================================

@router.get("/{dataset_id}/preview")
def get_dataset_preview(
    dataset_id: str,
    rows: int = 3,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get dataset preview with headers and first N rows
    
    Args:
        dataset_id: Dataset UUID
        rows: Number of rows to preview (default 3, max 100)
    
    Returns:
        - columns: List of column names
        - column_types: Dict of column name -> data type
        - preview_data: First N rows as list of dicts
        - total_rows: Total row count
        - metadata: File info (size, uploaded_at, etc.)
    """
    
    # Limit rows to prevent abuse
    rows = min(rows, 100)
    
    # Get dataset from DB
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.tenant_id == current_user.tenant_id
    ).first()
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found"
        )
    
    # Check if file exists
    if not os.path.exists(dataset.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset file not found on disk. Please re-upload."
        )
    
    # Read preview data
    try:
        file_ext = os.path.splitext(dataset.original_filename)[1].lower()
        
        if file_ext == '.csv':
            # Try European format first (semicolon delimiter, comma decimal)
            try:
                df = pd.read_csv(
                    dataset.file_path,
                    nrows=rows,
                    sep=';',
                    decimal=',',
                    encoding='utf-8',
                    low_memory=False
                )
                # Check if we got reasonable data (more than 1 column)
                if len(df.columns) <= 1:
                    raise ValueError("Only 1 column detected, trying different format")
            except:
                # Fallback to standard CSV format
                try:
                    df = pd.read_csv(
                        dataset.file_path,
                        nrows=rows,
                        encoding='utf-8',
                        low_memory=False
                    )
                except:
                    # Try Windows encoding
                    df = pd.read_csv(
                        dataset.file_path,
                        nrows=rows,
                        encoding='windows-1250',
                        sep=';',
                        decimal=',',
                        low_memory=False
                    )
        else:
            df = pd.read_excel(dataset.file_path, nrows=rows)
        
        # Convert to preview format
        columns = df.columns.tolist()
        column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # Convert DataFrame to list of dicts, handling NaN values
        preview_data = df.fillna("").to_dict(orient='records')
        
        # Format values for display
        for row in preview_data:
            for key, value in row.items():
                if pd.isna(value):
                    row[key] = ""
                elif isinstance(value, float):
                    # Format large numbers with spaces
                    if abs(value) >= 1000:
                        row[key] = f"{value:,.0f}".replace(",", " ")
                    else:
                        row[key] = f"{value:.2f}" if value % 1 != 0 else str(int(value))
                else:
                    row[key] = str(value)
        
        return {
            "id": str(dataset.id),
            "filename": dataset.original_filename,
            "columns": columns,
            "column_types": column_types,
            "column_count": len(columns),
            "preview_data": preview_data,
            "preview_rows": len(preview_data),
            "total_rows": dataset.rows,
            "metadata": {
                "size_mb": round(dataset.file_size_bytes / (1024 * 1024), 2),
                "uploaded_at": dataset.uploaded_at.isoformat(),
                "last_used_at": dataset.last_used_at.isoformat() if dataset.last_used_at else None
            }
        }
        
    except Exception as e:
        print(f"❌ Error reading dataset preview: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read dataset: {str(e)}"
        )


# ==========================================
# 🆕 LIST ALL DATASETS WITH PREVIEW
# ==========================================

@router.get("/all/with-preview")
def list_datasets_with_preview(
    preview_rows: int = 3,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all datasets with preview data included
    
    This is a convenience endpoint that returns all datasets
    with their preview data in a single request.
    
    Args:
        preview_rows: Number of rows to include in preview (default 3, max 10)
    
    Returns:
        List of datasets with preview data
    """
    
    # Limit preview rows
    preview_rows = min(preview_rows, 10)
    
    datasets = db.query(Dataset).filter(
        Dataset.tenant_id == current_user.tenant_id
    ).order_by(Dataset.uploaded_at.desc()).all()
    
    result = []
    
    for dataset in datasets:
        dataset_info = {
            "id": str(dataset.id),
            "filename": dataset.original_filename,
            "size_mb": round(dataset.file_size_bytes / (1024 * 1024), 2),
            "rows": dataset.rows,
            "columns": list(dataset.columns.keys()) if dataset.columns else [],
            "column_types": dataset.columns if dataset.columns else {},
            "uploaded_at": dataset.uploaded_at.isoformat(),
            "last_used_at": dataset.last_used_at.isoformat() if dataset.last_used_at else None,
            "preview_data": None,
            "preview_error": None
        }
        
        # Try to load preview data
        if os.path.exists(dataset.file_path):
            try:
                file_ext = os.path.splitext(dataset.original_filename)[1].lower()
                
                if file_ext == '.csv':
                    try:
                        df = pd.read_csv(
                            dataset.file_path,
                            nrows=preview_rows,
                            sep=';',
                            decimal=',',
                            encoding='utf-8',
                            low_memory=False
                        )
                        if len(df.columns) <= 1:
                            raise ValueError("Retry with different format")
                    except:
                        try:
                            df = pd.read_csv(
                                dataset.file_path,
                                nrows=preview_rows,
                                encoding='utf-8',
                                low_memory=False
                            )
                        except:
                            df = pd.read_csv(
                                dataset.file_path,
                                nrows=preview_rows,
                                encoding='windows-1250',
                                sep=';',
                                decimal=',',
                                low_memory=False
                            )
                else:
                    df = pd.read_excel(dataset.file_path, nrows=preview_rows)
                
                # Convert to preview format
                preview_data = df.fillna("").to_dict(orient='records')
                
                # Format values
                for row in preview_data:
                    for key, value in row.items():
                        if pd.isna(value):
                            row[key] = ""
                        elif isinstance(value, float):
                            if abs(value) >= 1000:
                                row[key] = f"{value:,.0f}".replace(",", " ")
                            else:
                                row[key] = f"{value:.2f}" if value % 1 != 0 else str(int(value))
                        else:
                            row[key] = str(value)
                
                dataset_info["preview_data"] = preview_data
                dataset_info["columns"] = df.columns.tolist()
                dataset_info["column_types"] = {col: str(dtype) for col, dtype in df.dtypes.items()}
                
            except Exception as e:
                dataset_info["preview_error"] = str(e)
        else:
            dataset_info["preview_error"] = "File not found on disk"
        
        result.append(dataset_info)
    
    return {
        "total": len(result),
        "datasets": result
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
