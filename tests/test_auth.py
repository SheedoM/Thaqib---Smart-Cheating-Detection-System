def test_login_success(client, admin_user):
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_failure(client, admin_user):
    response = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect username or password"

def test_read_me_success(client, admin_user, admin_token_headers):
    response = client.get("/api/auth/me", headers=admin_token_headers)
    assert response.status_code == 200
    assert response.json()["username"] == admin_user.username

def test_read_me_unauthorized(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
