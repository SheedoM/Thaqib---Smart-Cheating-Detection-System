from slowapi import Limiter
from slowapi.util import get_remote_address

from src.thaqib.config.settings import get_settings

settings = get_settings()

# Initialize Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    enabled=settings.app_env != "testing",
)
