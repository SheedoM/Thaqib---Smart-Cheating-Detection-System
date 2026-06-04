from datetime import datetime, timedelta, timezone

from src.thaqib.db.models.exams import Assignment, ExamSession
from src.thaqib.db.models.infrastructure import Hall


def _create_hall(client, headers, institution_id, name):
    response = client.post(
        "/api/halls/",
        json={
            "name": name,
            "capacity": 40,
            "institution_id": str(institution_id),
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_device(client, headers, hall_id, identifier, device_type, **extra):
    payload = {
        "hall_id": hall_id,
        "identifier": identifier,
        "type": device_type,
        "status": extra.pop("status", "offline"),
        "position": {"label": identifier},
        **extra,
    }
    response = client.post("/api/devices/", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_exam_session_returns_halls_and_assignments(
    client,
    admin_token_headers,
    test_institution,
    invigilator_user,
):
    hall_a = _create_hall(client, admin_token_headers, test_institution.id, "Hall A")
    hall_b = _create_hall(client, admin_token_headers, test_institution.id, "Hall B")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    create_response = client.post(
        "/api/sessions/",
        json={
            "exam_name": "Database Systems",
            "exam_type": "final",
            "scheduled_start": start.isoformat(),
            "scheduled_end": end.isoformat(),
            "student_count": 80,
            "hall_ids": [hall_a["id"]],
            "configuration": {"period": "الفترة الأولي"},
        },
        headers=admin_token_headers,
    )
    assert create_response.status_code == 201
    session = create_response.json()
    assert session["halls"] == [{"id": hall_a["id"], "name": "Hall A"}]

    update_response = client.put(
        f"/api/sessions/{session['id']}",
        json={"hall_ids": [hall_b["id"]]},
        headers=admin_token_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["halls"] == [{"id": hall_b["id"], "name": "Hall B"}]

    assignment_response = client.post(
        f"/api/sessions/{session['id']}/assignments",
        json={
            "invigilator_id": str(invigilator_user.id),
            "hall_id": hall_b["id"],
            "role": "primary",
        },
        headers=admin_token_headers,
    )
    assert assignment_response.status_code == 201

    read_response = client.get(f"/api/sessions/{session['id']}", headers=admin_token_headers)
    assert read_response.status_code == 200
    body = read_response.json()
    assert body["halls"] == [{"id": hall_b["id"], "name": "Hall B"}]
    assert body["assignments"][0]["hall_id"] == hall_b["id"]
    assert body["assignments"][0]["invigilator_id"] == str(invigilator_user.id)


def test_hall_readiness_returns_device_checks(
    client,
    admin_user,
    test_institution,
    invigilator_user,
):
    admin_login = client.post(
        "/api/auth/login",
        data={"username": admin_user.username, "password": "securepassword"},
    )
    assert admin_login.status_code == 200
    admin_token_headers = {"X-CSRF-Token": admin_login.json()["csrf_token"]}

    hall = _create_hall(client, admin_token_headers, test_institution.id, "Readiness Hall")
    _create_device(
        client,
        admin_token_headers,
        hall["id"],
        "camera-main",
        "camera",
        stream_url="missing-video-source.mp4",
    )
    _create_device(
        client,
        admin_token_headers,
        hall["id"],
        "mic-main",
        "microphone",
        status="online",
    )
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)

    create_response = client.post(
        "/api/sessions/",
        json={
            "exam_name": "Readiness Exam",
            "exam_type": "midterm",
            "scheduled_start": start.isoformat(),
            "scheduled_end": end.isoformat(),
            "student_count": 30,
            "hall_ids": [hall["id"]],
        },
        headers=admin_token_headers,
    )
    assert create_response.status_code == 201
    session = create_response.json()

    assignment_response = client.post(
        f"/api/sessions/{session['id']}/assignments",
        json={
            "invigilator_id": str(invigilator_user.id),
            "hall_id": hall["id"],
            "role": "primary",
        },
        headers=admin_token_headers,
    )
    assert assignment_response.status_code == 201

    invigilator_login = client.post(
        "/api/auth/login",
        data={"username": invigilator_user.username, "password": "securepassword"},
    )
    assert invigilator_login.status_code == 200
    invigilator_token_headers = {"X-CSRF-Token": invigilator_login.json()["csrf_token"]}

    readiness_response = client.get(
        f"/api/sessions/{session['id']}/halls/{hall['id']}/readiness",
        headers=invigilator_token_headers,
    )
    assert readiness_response.status_code == 200
    body = readiness_response.json()
    assert body["overall_status"] == "warning"
    assert body["failed_count"] == 2
    assert {device["type"] for device in body["devices"]} == {"camera", "microphone", "voice"}


def test_hall_readiness_accepts_assignment_backed_seed_link(
    client,
    db_session,
    test_institution,
    invigilator_user,
    invigilator_token_headers,
):
    hall = Hall(
        institution_id=test_institution.id,
        name="Legacy Seed Hall",
        capacity=40,
        status="ready",
    )
    session = ExamSession(
        exam_name="Midterm Exam 2024",
        exam_type="Final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(minutes=30),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=2),
        status="scheduled",
        student_count=100,
    )
    assignment = Assignment(
        exam_session=session,
        hall=hall,
        invigilator=invigilator_user,
        role="primary",
    )
    db_session.add_all([hall, session, assignment])
    db_session.commit()

    response = client.get(
        f"/api/sessions/{session.id}/halls/{hall.id}/readiness",
        headers=invigilator_token_headers,
    )

    assert response.status_code == 200
    assert response.json()["hall_id"] == str(hall.id)
