def test_login_sets_session_cookies(client, admin_user):
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "cookie"
    assert "csrf_token" in data
    assert "thaqib_access_token" in response.cookies
    assert "thaqib_refresh_token" in response.cookies

def test_refresh_token_flow(client, admin_user):
    login_response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert login_response.status_code == 200
    csrf_token = login_response.json()["csrf_token"]
    
    refresh_response = client.post(
        "/api/auth/refresh",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert data["token_type"] == "cookie"
    assert data["csrf_token"] != csrf_token
    
    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == admin_user.username

def test_refresh_with_invalid_token(client):
    response = client.post(
        "/api/auth/refresh",
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"

def test_csrf_required_for_cookie_refresh(client, admin_user):
    login_response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert login_response.status_code == 200

    response = client.post(
        "/api/auth/refresh",
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF token missing or invalid"

def test_logout_revokes_cookie_session(client, admin_user):
    login_response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert login_response.status_code == 200
    response = client.post(
        "/api/auth/logout",
        headers={"X-CSRF-Token": login_response.json()["csrf_token"]},
    )
    assert response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

def test_rbac_admin_access(client, admin_token_headers):
    # Institutions index is admin-only
    response = client.get("/api/institutions/", headers=admin_token_headers)
    assert response.status_code == 200
