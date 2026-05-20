import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from src.thaqib.config.settings import get_settings
from src.thaqib.core.security import decode_token
from src.thaqib.db.database import get_db
from src.thaqib.db.models.users import User

settings = get_settings()

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = None
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    if not token:
        token = request.cookies.get(settings.access_cookie_name)
    if not token:
        raise credentials_exception

    payload = decode_token(token)
    if not payload:
        raise credentials_exception
    username: str | None = payload.get("sub")
    token_type: str | None = payload.get("type")
    if username is None or token_type != "access":
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.status != "active":
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

class RequireRole:
    """Dependency injection to check if the current user has the required roles."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
        
    def __call__(self, current_user: User = Depends(get_current_active_user)):
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires roles: {self.allowed_roles}",
            )
        return current_user

def require_internal_event_token(request: Request) -> None:
    """Authenticate machine-to-machine event ingestion."""
    expected = settings.internal_event_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal event token is not configured",
        )

    provided = request.headers.get("X-Thaqib-Internal-Token")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal event token",
        )
