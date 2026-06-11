from pathlib import Path


def test_user_image_upload_and_persistence(client, super_admin_token_headers, test_institution):
    response = client.post(
        "/api/users/upload-image",
        files={"image": ("avatar.png", b"\x89PNG\r\n\x1a\nfake", "image/png")},
        headers=super_admin_token_headers,
    )
    assert response.status_code == 200
    image_url = response.json()["url"]
    assert image_url.startswith("/uploads/users/")

    created_path = Path(image_url.lstrip("/"))
    try:
        create_response = client.post(
            "/api/users/",
            json={
                "institution_id": str(test_institution.id),
                "username": "invig_image",
                "full_name": "Image Invigilator",
                "email": "image-invig@test.com",
                "password": "securepassword",
                "role": "invigilator",
                "image": image_url,
            },
            headers=super_admin_token_headers,
        )
        assert create_response.status_code == 201
        assert create_response.json()["image"] == image_url
    finally:
        if created_path.exists():
            created_path.unlink()


def test_user_image_upload_rejects_invalid_type(client, super_admin_token_headers):
    response = client.post(
        "/api/users/upload-image",
        files={"image": ("avatar.txt", b"not-an-image", "text/plain")},
        headers=super_admin_token_headers,
    )
    assert response.status_code == 400
