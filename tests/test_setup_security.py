from src.thaqib.config.settings import get_settings


def _setup_payload() -> dict[str, str]:
    return {
        "institution_name": "Secure University",
        "admin": "Root Admin",
        "admin_password": "VerySecure123!",
    }


def _configure_production_setup(monkeypatch, token: str) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.setenv("SECRET_KEY", "production-secret-key-with-at-least-32-chars")
    monkeypatch.setenv("INTERNAL_EVENT_TOKEN", "internal-event-token-at-least-24")
    monkeypatch.setenv("SETUP_BOOTSTRAP_TOKEN", token)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("CORS_ORIGINS", "https://thaqib.example.edu")
    monkeypatch.setenv("DATABASE_URL", "postgresql://thaqib:secret@db:5432/thaqib")


def test_setup_requires_admin_password_and_does_not_return_plaintext(client):
    response = client.post(
        "/api/setup/install",
        json=_setup_payload(),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["generated_credentials"]["username"] == "root_admin"
    assert "password" not in data["generated_credentials"]


def test_setup_rejects_short_admin_password(client):
    response = client.post(
        "/api/setup/install",
        json={
            "institution_name": "Secure University",
            "admin": "Root Admin",
            "admin_password": "short",
        },
    )

    assert response.status_code == 422


def test_setup_requires_configured_bootstrap_token(client, monkeypatch):
    monkeypatch.setenv("SETUP_BOOTSTRAP_TOKEN", "test-bootstrap-token-at-least-24")
    get_settings.cache_clear()
    try:
        response = client.post("/api/setup/install", json=_setup_payload())
    finally:
        get_settings.cache_clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid or missing setup bootstrap token"


def test_setup_accepts_matching_bootstrap_token(client, monkeypatch):
    token = "test-bootstrap-token-at-least-24"
    monkeypatch.setenv("SETUP_BOOTSTRAP_TOKEN", token)
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/setup/install",
            json=_setup_payload(),
            headers={"X-Thaqib-Setup-Token": token},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 201


def test_production_setup_rejects_public_forwarded_ip(client, monkeypatch):
    token = "test-bootstrap-token-at-least-24"
    _configure_production_setup(monkeypatch, token)
    get_settings.cache_clear()
    try:
        response = client.post(
            "/api/setup/install",
            json=_setup_payload(),
            headers={
                "X-Thaqib-Setup-Token": token,
                "X-Forwarded-For": "8.8.8.8",
            },
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Setup is only allowed from localhost or a private network"
