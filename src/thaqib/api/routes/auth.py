from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Any

from src.thaqib.db.database import get_db
from src.thaqib.db.models.users import User
from src.thaqib.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from src.thaqib.schemas.users import Token, UserResponse, TokenData
from src.thaqib.api.dependencies import get_current_active_user
from src.thaqib.core.limiter import limiter

router = APIRouter()

@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login_access_token(
    request: Request,
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    
    access_token = create_access_token(subject=user.username)
    refresh_token = create_refresh_token(subject=user.username)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
@limiter.limit("5/minute")
def refresh_token(
    request: Request,
    refresh_token: str,
    db: Session = Depends(get_db)
) -> Any:
    """
    Exchange a refresh token for a new access token.
    """
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
        
    new_access_token = create_access_token(subject=user.username)
    # We can also rotate the refresh token here if desired
    new_refresh_token = create_refresh_token(subject=user.username)
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }

@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get current user profile.
    """
    return current_user


@router.get("/me-debug")
def read_users_me_debug(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Debug version of /me which returns a simple JSON dict of user attributes.
    Use this to isolate serialization issues from dependency/auth failures.
    """
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "status": current_user.status,
    }
