from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.users import RefreshToken, User
from src.thaqib.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token_id,
    new_csrf_token,
    new_token_id,
    verify_password,
)
from src.thaqib.config.settings import get_settings
from src.thaqib.schemas.users import SessionResponse, UserResponse
from src.thaqib.api.dependencies import get_current_active_user
from src.thaqib.core.limiter import limiter

router = APIRouter()
settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _refresh_expires_at() -> datetime:
    return _now() + timedelta(days=settings.refresh_token_expire_days)


def _is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= _now()


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    response.set_cookie(
        settings.access_cookie_name,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    for cookie_name in (
        settings.access_cookie_name,
        settings.refresh_cookie_name,
        settings.csrf_cookie_name,
    ):
        response.delete_cookie(cookie_name, path="/")


def _issue_session(db: Session, response: Response, user: User) -> dict[str, Any]:
    csrf_token = new_csrf_token()
    refresh_jti = new_token_id()
    refresh_hash = hash_token_id(refresh_jti)
    access_token = create_access_token(subject=user.username)
    refresh_token = create_refresh_token(subject=user.username, jti=refresh_jti)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=_refresh_expires_at(),
        )
    )
    db.commit()

    _set_auth_cookies(response, access_token, refresh_token, csrf_token)
    return {"token_type": "cookie", "csrf_token": csrf_token, "user": user}


@router.post("/login", response_model=SessionResponse)
@limiter.limit("5/minute")
def login_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db), 
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    Login and set HttpOnly access/refresh cookies plus a readable CSRF cookie.
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
    return _issue_session(db, response, user)


@router.post("/refresh", response_model=SessionResponse)
@limiter.limit("5/minute")
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
) -> Any:
    """
    Rotate the HttpOnly refresh cookie and issue a new access cookie.
    """
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    username = payload.get("sub")
    token_hash = hash_token_id(payload.get("jti", ""))
    user = db.query(User).filter(User.username == username).first()
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not stored or stored.revoked_at is not None or _is_expired(stored.expires_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    new_jti = new_token_id()
    new_hash = hash_token_id(new_jti)
    stored.revoked_at = _now()
    stored.replaced_by_hash = new_hash

    csrf_token = new_csrf_token()
    access_token = create_access_token(subject=user.username)
    new_refresh_token = create_refresh_token(subject=user.username, jti=new_jti)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=_refresh_expires_at(),
        )
    )
    db.commit()

    _set_auth_cookies(response, access_token, new_refresh_token, csrf_token)
    return {"token_type": "cookie", "csrf_token": csrf_token, "user": user}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload and payload.get("jti"):
            token_hash = hash_token_id(payload["jti"])
            stored = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
            if stored and stored.revoked_at is None:
                stored.revoked_at = _now()
                db.commit()

    _clear_auth_cookies(response)
    return {"message": "Logged out"}

@router.get("/me", response_model=UserResponse)
def read_users_me(
    current_user: User = Depends(get_current_active_user)
) -> Any:
    """
    Get current user profile.
    """
    return current_user

