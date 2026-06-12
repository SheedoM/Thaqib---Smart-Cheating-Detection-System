from src.thaqib.api.routes.stream import _serialize_camera
from src.thaqib.db.models.infrastructure import Device, Hall


def test_create_institution_as_super_admin(client, super_admin_token_headers):
    data = {"name": "Test Inst", "code": "TST"}
    response = client.post("/api/institutions/", json=data, headers=super_admin_token_headers)
    assert response.status_code == 201
    assert response.json()["code"] == "TST"

def test_create_institution_as_admin_is_forbidden(client, admin_token_headers):
    data = {"name": "Test Inst", "code": "TST"}
    response = client.post("/api/institutions/", json=data, headers=admin_token_headers)
    assert response.status_code == 403
    assert "roles: ['super_admin']" in response.json()["detail"]

def test_create_institution_as_invigilator(client, invigilator_token_headers):
    data = {"name": "Test Inst", "code": "TST"}
    response = client.post("/api/institutions/", json=data, headers=invigilator_token_headers)
    assert response.status_code == 403
    assert "roles: ['super_admin']" in response.json()["detail"]

def test_create_hall_as_super_admin(client, super_admin_token_headers, test_institution):
    data = {"name": "Hall A", "capacity": 50, "institution_id": str(test_institution.id)}
    response = client.post("/api/halls/", json=data, headers=super_admin_token_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Hall A"

def test_create_hall_as_admin_in_own_institution(client, admin_token_headers, test_institution):
    data = {"name": "Hall A", "capacity": 50, "institution_id": str(test_institution.id)}
    response = client.post("/api/halls/", json=data, headers=admin_token_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Hall A"

def test_create_hall_as_invigilator(client, invigilator_token_headers, test_institution):
    data = {"name": "Hall B", "capacity": 30, "institution_id": str(test_institution.id)}
    response = client.post("/api/halls/", json=data, headers=invigilator_token_headers)
    assert response.status_code == 403


def test_admin_can_manage_devices_in_own_hall(client, admin_token_headers, test_institution):
    hall_response = client.post(
        "/api/halls/",
        json={"name": "Device Admin Hall", "capacity": 40, "institution_id": str(test_institution.id)},
        headers=admin_token_headers,
    )
    assert hall_response.status_code == 201
    hall_id = hall_response.json()["id"]

    create_response = client.post(
        "/api/devices/",
        json={
            "hall_id": hall_id,
            "type": "camera",
            "identifier": "admin-camera-1",
            "stream_url": "0",
            "position": {"label": "Front"},
        },
        headers=admin_token_headers,
    )
    assert create_response.status_code == 201
    device_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/devices/{device_id}",
        json={"status": "online"},
        headers=admin_token_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "online"


def test_admin_can_read_and_update_own_institution(client, admin_token_headers, test_institution):
    read_response = client.get("/api/institutions/", headers=admin_token_headers)
    assert read_response.status_code == 200
    assert [item["id"] for item in read_response.json()] == [str(test_institution.id)]

    update_response = client.put(
        f"/api/institutions/{test_institution.id}",
        json={"name": "Updated College", "code": test_institution.code},
        headers=admin_token_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Updated College"


def test_admin_can_read_system_settings(client, admin_token_headers):
    response = client.get("/api/settings/", headers=admin_token_headers)

    assert response.status_code == 200
    assert "video_quality" in response.json()


def test_camera_without_stream_url_serializes_as_offline(db_session, test_institution):
    hall = Hall(
        institution_id=test_institution.id,
        name="Offline Source Hall",
        capacity=30,
        status="ready",
    )
    camera = Device(
        hall=hall,
        type="camera",
        identifier="offline-source-camera",
        stream_url=None,
        position={"label": "Offline Source"},
        status="online",
    )
    db_session.add_all([hall, camera])
    db_session.commit()

    payload = _serialize_camera(camera, hall, runtime=None)

    assert payload["status"] == "offline"
    assert payload["feed_path"] is None
    assert payload["source_configured"] is False
