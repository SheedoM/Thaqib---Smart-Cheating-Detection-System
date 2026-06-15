import pytest
from pydantic import ValidationError

from src.thaqib.config.settings import Settings


def _production_settings(**overrides):
    data = {
        "app_env": "production",
        "debug": False,
        "secret_key": "production-secret-key-with-at-least-32-chars",
        "internal_event_token": "internal-event-token-at-least-24",
        "setup_bootstrap_token": "setup-bootstrap-token-at-least-24",
        "cookie_secure": True,
        "cors_origins": ["https://thaqib.example.edu"],
        "database_url": "postgresql://thaqib:secret@db:5432/thaqib",
    }
    data.update(overrides)
    return Settings(**data)


def test_production_settings_accept_hardened_configuration():
    settings = _production_settings()

    assert settings.app_env == "production"


def test_cors_origins_accept_comma_separated_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://thaqib.example.edu,https://admin.example.edu")

    settings = Settings()

    assert settings.cors_origins == ["https://thaqib.example.edu", "https://admin.example.edu"]


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"cookie_secure": False}, "COOKIE_SECURE must be true in production"),
        ({"database_url": "sqlite:///./data/thaqib.db"}, "SQLite is not allowed in production"),
        ({"setup_bootstrap_token": None}, "SETUP_BOOTSTRAP_TOKEN must be configured in production"),
        ({"setup_bootstrap_token": "short"}, "SETUP_BOOTSTRAP_TOKEN must be configured in production"),
    ],
)
def test_production_settings_reject_unsafe_deployment_values(override, message):
    with pytest.raises(ValidationError, match=message):
        _production_settings(**override)
