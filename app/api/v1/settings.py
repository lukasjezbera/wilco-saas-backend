"""
Settings API Endpoints
Manage tenant-specific settings including AI prompts
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.tenant_settings import (
    TenantSettings,
    DEFAULT_COMPANY_CONTEXT,
    DEFAULT_ANALYST_ROLE,
    DEFAULT_OUTPUT_STRUCTURE,
    DEFAULT_ANALYSIS_RULES,
    DEFAULT_TOPIC_CONTEXTS
)
from app.api.v1.auth import get_current_user


router = APIRouter(prefix="/settings", tags=["Settings"])


# ==========================================
# SCHEMAS
# ==========================================

class SettingsResponse(BaseModel):
    company_context: str
    analyst_role: str
    output_structure: str
    analysis_rules: str
    topic_contexts: Dict[str, str]
    updated_at: Optional[str] = None

class SettingsUpdateRequest(BaseModel):
    company_context: Optional[str] = None
    analyst_role: Optional[str] = None
    output_structure: Optional[str] = None
    analysis_rules: Optional[str] = None
    topic_contexts: Optional[Dict[str, str]] = None


# ==========================================
# GET SETTINGS
# ==========================================

@router.get("/", response_model=SettingsResponse)
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current tenant settings
    Returns defaults if no custom settings exist
    """
    
    settings = db.query(TenantSettings).filter(
        TenantSettings.tenant_id == current_user.tenant_id
    ).first()
    
    if settings:
        return SettingsResponse(
            company_context=settings.company_context or DEFAULT_COMPANY_CONTEXT,
            analyst_role=settings.analyst_role or DEFAULT_ANALYST_ROLE,
            output_structure=settings.output_structure or DEFAULT_OUTPUT_STRUCTURE,
            analysis_rules=settings.analysis_rules or DEFAULT_ANALYSIS_RULES,
            topic_contexts=settings.topic_contexts or DEFAULT_TOPIC_CONTEXTS,
            updated_at=settings.updated_at.isoformat() if settings.updated_at else None
        )
    else:
        # Return defaults
        return SettingsResponse(
            company_context=DEFAULT_COMPANY_CONTEXT,
            analyst_role=DEFAULT_ANALYST_ROLE,
            output_structure=DEFAULT_OUTPUT_STRUCTURE,
            analysis_rules=DEFAULT_ANALYSIS_RULES,
            topic_contexts=DEFAULT_TOPIC_CONTEXTS,
            updated_at=None
        )


# ==========================================
# UPDATE SETTINGS
# ==========================================

@router.put("/", response_model=SettingsResponse)
def update_settings(
    request: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update tenant settings
    Only provided fields will be updated
    """
    
    settings = db.query(TenantSettings).filter(
        TenantSettings.tenant_id == current_user.tenant_id
    ).first()
    
    if not settings:
        # Create new settings record
        settings = TenantSettings(
            tenant_id=current_user.tenant_id,
            company_context=DEFAULT_COMPANY_CONTEXT,
            analyst_role=DEFAULT_ANALYST_ROLE,
            output_structure=DEFAULT_OUTPUT_STRUCTURE,
            analysis_rules=DEFAULT_ANALYSIS_RULES,
            topic_contexts=DEFAULT_TOPIC_CONTEXTS
        )
        db.add(settings)
    
    # Update only provided fields
    if request.company_context is not None:
        settings.company_context = request.company_context
    if request.analyst_role is not None:
        settings.analyst_role = request.analyst_role
    if request.output_structure is not None:
        settings.output_structure = request.output_structure
    if request.analysis_rules is not None:
        settings.analysis_rules = request.analysis_rules
    if request.topic_contexts is not None:
        settings.topic_contexts = request.topic_contexts
    
    settings.updated_by = current_user.id
    settings.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(settings)
    
    return SettingsResponse(
        company_context=settings.company_context or DEFAULT_COMPANY_CONTEXT,
        analyst_role=settings.analyst_role or DEFAULT_ANALYST_ROLE,
        output_structure=settings.output_structure or DEFAULT_OUTPUT_STRUCTURE,
        analysis_rules=settings.analysis_rules or DEFAULT_ANALYSIS_RULES,
        topic_contexts=settings.topic_contexts or DEFAULT_TOPIC_CONTEXTS,
        updated_at=settings.updated_at.isoformat() if settings.updated_at else None
    )


# ==========================================
# RESET SETTINGS TO DEFAULTS
# ==========================================

@router.post("/reset", response_model=SettingsResponse)
def reset_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reset all settings to defaults
    """
    
    settings = db.query(TenantSettings).filter(
        TenantSettings.tenant_id == current_user.tenant_id
    ).first()
    
    if settings:
        settings.company_context = DEFAULT_COMPANY_CONTEXT
        settings.analyst_role = DEFAULT_ANALYST_ROLE
        settings.output_structure = DEFAULT_OUTPUT_STRUCTURE
        settings.analysis_rules = DEFAULT_ANALYSIS_RULES
        settings.topic_contexts = DEFAULT_TOPIC_CONTEXTS
        settings.updated_by = current_user.id
        settings.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(settings)
    
    return SettingsResponse(
        company_context=DEFAULT_COMPANY_CONTEXT,
        analyst_role=DEFAULT_ANALYST_ROLE,
        output_structure=DEFAULT_OUTPUT_STRUCTURE,
        analysis_rules=DEFAULT_ANALYSIS_RULES,
        topic_contexts=DEFAULT_TOPIC_CONTEXTS,
        updated_at=settings.updated_at.isoformat() if settings else None
    )


# ==========================================
# GET DEFAULTS (for reference)
# ==========================================

@router.get("/defaults", response_model=SettingsResponse)
def get_default_settings(
    current_user: User = Depends(get_current_user)
):
    """
    Get default settings values for reference
    Useful for resetting individual fields
    """
    
    return SettingsResponse(
        company_context=DEFAULT_COMPANY_CONTEXT,
        analyst_role=DEFAULT_ANALYST_ROLE,
        output_structure=DEFAULT_OUTPUT_STRUCTURE,
        analysis_rules=DEFAULT_ANALYSIS_RULES,
        topic_contexts=DEFAULT_TOPIC_CONTEXTS,
        updated_at=None
    )
