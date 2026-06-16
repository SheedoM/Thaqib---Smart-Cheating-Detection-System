import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Union
import jwt
from passlib.context import CryptContext
from src.thaqib.config.settings import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed one."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)

def create_access_token(
    subject: Union[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a short-lived JWT access token for a user."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def create_refresh_token(
    subject: Union[str, Any],
    jti: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a long-lived JWT refresh token for a user."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh", "jti": jti}
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except jwt.PyJWTError:
        return None

def new_token_id() -> str:
    """Generate a high-entropy opaque token identifier for refresh rotation."""
    return secrets.token_urlsafe(32)

def new_csrf_token() -> str:
    """Generate a readable CSRF token for double-submit cookie protection."""
    return secrets.token_urlsafe(32)

def hash_token_id(jti: str) -> str:
    """Store only a hash of refresh token identifiers."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()
