"""
Authentication API Endpoints
User signup, login, and token management
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.auth import UserSignup, UserLogin, UserWithToken, UserResponse
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token


router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ==========================================
# AUTHENTICATION DEPENDENCIES
# ==========================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        if payload is None:
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    return user


# ==========================================
# SIGNUP
# ==========================================

@router.post("/signup", response_model=UserWithToken, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """
    Register new user and create tenant
    
    Creates:
    - New tenant (company)
    - First user (admin) for that tenant
    
    Returns:
    - User data
    - Access token
    """
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create tenant (company)
    tenant = Tenant(
        name=user_data.company_name,
        created_at=datetime.utcnow()
    )
    db.add(tenant)
    db.flush()  # Get tenant.id without committing
    
    # Create user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        tenant_id=tenant.id,
        is_active=True,
        is_superuser=True,  # First user is admin
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return UserWithToken(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at
        ),
        access_token=access_token,
        token_type="bearer"
    )


# ==========================================
# LOGIN
# ==========================================

@router.post("/login", response_model=UserWithToken)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Login with email and password
    
    Returns:
    - User data
    - Access token
    """
    
    # Find user
    user = db.query(User).filter(User.email == credentials.email).first()
    
    # Verify credentials
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return UserWithToken(
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at
        ),
        access_token=access_token,
        token_type="bearer"
    )


# ==========================================
# GET CURRENT USER
# ==========================================

@router.get("/me", response_model=UserResponse)
def get_current_user_endpoint(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user
    
    Requires: Bearer token in Authorization header
    """
    return UserResponse.model_validate(current_user)
