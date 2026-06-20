from pathlib import Path

from src.thaqib.core.security import get_password_hash
from src.thaqib.db.models.users import User


def test_admin_can_create_invigilator_in_own_institution(client, admin_token_headers, test_institution):
    response = client.post(
        "/api/users/",
        json={
            "institution_id": str(test_institution.id),
            "username": "admin_created_invig",
            "full_name": "Admin Created Invigilator",
            "email": "admin-created-invig@test.com",
            "password": "securepassword",
            "role": "invigilator",
        },
        headers=admin_token_headers,
    )

    assert response.status_code == 201
    assert response.json()["role"] == "invigilator"


def test_admin_cannot_create_admin_user(client, admin_token_headers, test_institution):
    response = client.post(
        "/api/users/",
        json={
            "institution_id": str(test_institution.id),
            "username": "admin_created_admin",
            "full_name": "Admin Created Admin",
            "email": "admin-created-admin@test.com",
            "password": "securepassword",
            "role": "admin",
        },
        headers=admin_token_headers,
    )

    assert response.status_code == 403


def test_admin_can_update_invigilator_but_not_promote(
    client,
    db_session,
    admin_token_headers,
    test_institution,
):
    user = User(
        institution_id=test_institution.id,
        username="editable_invig",
        password_hash=get_password_hash("securepassword"),
        full_name="Editable Invigilator",
        email="editable-invig@test.com",
        role="invigilator",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    update = client.put(
        f"/api/users/{user.id}",
        json={"full_name": "Updated Invigilator"},
        headers=admin_token_headers,
    )
    assert update.status_code == 200
    assert update.json()["full_name"] == "Updated Invigilator"

    promote = client.put(
        f"/api/users/{user.id}",
        json={"role": "admin"},
        headers=admin_token_headers,
    )
    assert promote.status_code == 403


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


def test_invigilator_gets_default_preferences(client, invigilator_token_headers):
    response = client.get("/api/users/me/preferences", headers=invigilator_token_headers)

    assert response.status_code == 200
    assert response.json() == {
        "alert_cue_mode": "sound_vibrate",
        "alert_volume": 80,
        "browser_notifications_enabled": False,
        "compact_display": False,
        "large_text": False,
    }


def test_invigilator_preferences_are_saved_to_current_user(
    client,
    db_session,
    invigilator_token_headers,
    test_institution,
):
    update = client.put(
        "/api/users/me/preferences",
        json={
            "alert_cue_mode": "silent",
            "alert_volume": 0,
            "browser_notifications_enabled": True,
            "compact_display": True,
            "large_text": True,
        },
        headers=invigilator_token_headers,
    )
    assert update.status_code == 200
    assert update.json()["alert_cue_mode"] == "silent"
    assert update.json()["compact_display"] is True

    other = User(
        institution_id=test_institution.id,
        username="other_invig",
        password_hash=get_password_hash("securepassword"),
        full_name="Other Invigilator",
        email="other-invig@test.com",
        role="invigilator",
    )
    db_session.add(other)
    db_session.commit()

    login = client.post(
        "/api/auth/login",
        data={"username": "other_invig", "password": "securepassword"},
    )
    assert login.status_code == 200
    other_headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    other_response = client.get("/api/users/me/preferences", headers=other_headers)

    assert other_response.status_code == 200
    assert other_response.json()["alert_cue_mode"] == "sound_vibrate"
    assert other_response.json()["compact_display"] is False


def test_invigilator_preferences_validate_cue_mode_and_volume(
    client,
    invigilator_token_headers,
):
    bad_mode = client.put(
        "/api/users/me/preferences",
        json={
            "alert_cue_mode": "critical_only",
            "alert_volume": 80,
            "browser_notifications_enabled": False,
            "compact_display": False,
            "large_text": False,
        },
        headers=invigilator_token_headers,
    )
    bad_volume = client.put(
        "/api/users/me/preferences",
        json={
            "alert_cue_mode": "sound_only",
            "alert_volume": 101,
            "browser_notifications_enabled": False,
            "compact_display": False,
            "large_text": False,
        },
        headers=invigilator_token_headers,
    )

    assert bad_mode.status_code == 422
    assert bad_volume.status_code == 422


def test_user_preferences_are_invigilator_only(client, admin_token_headers):
    response = client.get("/api/users/me/preferences", headers=admin_token_headers)

    assert response.status_code == 403
