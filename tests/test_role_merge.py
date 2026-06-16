from datetime import datetime, timedelta, timezone

from src.thaqib.core.security import get_password_hash
from src.thaqib.db.models.exams import Assignment, ExamSession
from src.thaqib.db.models.infrastructure import Hall
from src.thaqib.db.models.users import User


def test_setup_creates_super_admin(client):
    response = client.post(
        "/api/setup/install",
        json={
            "institution_name": "Role Merge University",
            "admin": "Root Owner",
            "admin_password": "VerySecurePassword123!",
        },
    )

    assert response.status_code == 201
    login = client.post(
        "/api/auth/login",
        data={"username": "root_owner", "password": "VerySecurePassword123!"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "super_admin"


def test_referee_role_is_rejected(client, super_admin_token_headers, test_institution):
    response = client.post(
        "/api/users/",
        json={
            "institution_id": str(test_institution.id),
            "username": "legacy_referee",
            "email": "legacy-referee@test.com",
            "full_name": "Legacy Referee",
            "role": "referee",
            "password": "securepassword",
        },
        headers=super_admin_token_headers,
    )

    assert response.status_code == 422


def test_super_admin_observes_but_cannot_operate_exam(
    client,
    db_session,
    super_admin_token_headers,
    test_institution,
    invigilator_user,
):
    admin = User(
        institution_id=test_institution.id,
        username="exam_admin",
        password_hash=get_password_hash("securepassword"),
        full_name="Exam Admin",
        email="exam-admin@test.com",
        role="admin",
    )
    hall = Hall(institution_id=test_institution.id, name="Control Hall", capacity=30, status="ready")
    session = ExamSession(
        institution_id=test_institution.id,
        exam_name="Scoped Exam",
        exam_type="final",
        scheduled_start=datetime.now(timezone.utc) + timedelta(days=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
        status="scheduled",
        student_count=30,
    )
    session.halls = [hall]
    assignment = Assignment(exam_session=session, hall=hall, invigilator=invigilator_user, role="primary")
    db_session.add_all([admin, hall, session, assignment])
    db_session.commit()

    read_response = client.get(f"/api/sessions/{session.id}", headers=super_admin_token_headers)
    assert read_response.status_code == 200

    start_response = client.post(
        f"/api/sessions/{session.id}/halls/{hall.id}/monitoring/start",
        headers=super_admin_token_headers,
    )
    assert start_response.status_code == 403


def test_admin_sees_only_assigned_exams(
    client,
    db_session,
    admin_user,
    admin_token_headers,
    test_institution,
):
    assigned = ExamSession(
        institution_id=test_institution.id,
        exam_name="Assigned Exam",
        exam_type="final",
        scheduled_start=datetime.now(timezone.utc) + timedelta(days=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(days=1, hours=2),
        status="scheduled",
    )
    unassigned = ExamSession(
        institution_id=test_institution.id,
        exam_name="Unassigned Exam",
        exam_type="final",
        scheduled_start=datetime.now(timezone.utc) + timedelta(days=2),
        scheduled_end=datetime.now(timezone.utc) + timedelta(days=2, hours=2),
        status="scheduled",
    )
    db_session.add_all([assigned, unassigned])
    db_session.flush()

    from src.thaqib.db.models.exams import ExamAdminAssignment

    db_session.add(
        ExamAdminAssignment(
            exam_session_id=assigned.id,
            admin_id=admin_user.id,
            assignment_role="lead",
            assigned_by=admin_user.id,
        )
    )
    db_session.commit()

    response = client.get("/api/sessions/", headers=admin_token_headers)

    assert response.status_code == 200
    names = {item["exam_name"] for item in response.json()}
    assert names == {"Assigned Exam"}
