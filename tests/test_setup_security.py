def test_setup_requires_admin_password_and_does_not_return_plaintext(client):
    response = client.post(
        "/api/setup/install",
        json={
            "institution_name": "Secure University",
            "admin": "Root Admin",
            "admin_password": "VerySecure123!",
        },
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
