from datetime import datetime, timedelta, timezone


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
