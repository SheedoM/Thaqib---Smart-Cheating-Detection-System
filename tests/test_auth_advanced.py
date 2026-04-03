
import pytest
from src.thaqib.core.security import create_access_token

def test_login_returns_refresh_token(client, admin_user):
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_refresh_token_flow(client, admin_user):
    # 1. Login to get refresh token
    login_response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]
    
    # 2. Use refresh token to get new access token
    refresh_response = client.post(
        "/api/auth/refresh",
        params={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    
    # 3. Verify new access token works
    new_access_token = data["access_token"]
    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == admin_user.username

def test_refresh_with_invalid_token(client):
    response = client.post(
        "/api/auth/refresh",
        params={"refresh_token": "invalid_token_here"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"

def test_access_token_cannot_be_used_to_refresh(client, admin_user):
    # Get an access token
    login_response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    access_token = login_response.json()["access_token"]
    
    # Try to use access token as refresh token
    response = client.post(
        "/api/auth/refresh",
        params={"refresh_token": access_token}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"

def test_rbac_admin_access(client, admin_token_headers):
    # Institutions index is admin-only
    response = client.get("/api/institutions/", headers=admin_token_headers)
    assert response.status_code == 200
