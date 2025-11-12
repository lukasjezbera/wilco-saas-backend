"""
Authentication Schemas
Pydantic models for auth requests/responses
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


# ==========================================
# REQUEST SCHEMAS
# ==========================================

class UserSignup(BaseModel):
    """User signup request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, description="User's full name")
    company_name: str = Field(..., description="Company/organization name")


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


# ==========================================
# RESPONSE SCHEMAS
# ==========================================

class Token(BaseModel):
    """JWT token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class UserResponse(BaseModel):
    """User data response"""
    id: str = Field(..., description="User UUID")
    email: str = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_active: bool = Field(..., description="User is active")
    is_superuser: bool = Field(..., description="User is superuser")
    created_at: datetime = Field(..., description="Account creation date")
    
    class Config:
        from_attributes = True


class UserWithToken(BaseModel):
    """User data with access token"""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


# ==========================================
# INTERNAL SCHEMAS
# ==========================================

class TokenData(BaseModel):
    """Data extracted from JWT token"""
    user_id: Optional[str] = None
