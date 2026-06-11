from datetime import datetime, timedelta, timezone

from seed_demo import seed_college, seed_university
from scripts.seed_demo import upsert_assignment
from src.thaqib.db.models.exams import ExamAdminAssignment, ExamSession
from src.thaqib.db.models.infrastructure import Hall
from src.thaqib.db.models.users import User


def test_seed_assignment_links_hall_to_exam_session(db_session, test_institution, invigilator_user):
    hall = Hall(
        institution_id=test_institution.id,
        name="Seed Hall",
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
    db_session.add_all([hall, session])
    db_session.commit()

    upsert_assignment(db_session, session, invigilator_user, hall)
    db_session.refresh(session)

    assert [linked_hall.id for linked_hall in session.halls] == [hall.id]


def test_university_seed_has_one_super_admin_and_college_admins_are_admins(db_session):
    seed_university(db_session)

    users = db_session.query(User).all()
    users_by_username = {user.username: user for user in users}

    assert [user.username for user in users if user.role == "super_admin"] == ["admin"]
    assert users_by_username["admin_cs"].role == "admin"
    assert users_by_username["admin_eng"].role == "admin"
    assert users_by_username["admin_bus"].role == "admin"

    sessions = db_session.query(ExamSession).all()
    admin_assignments = db_session.query(ExamAdminAssignment).all()

    assert len(sessions) == 27
    assert len(admin_assignments) == len(sessions)

    assignments_by_admin = {
        username: db_session.query(ExamAdminAssignment)
        .filter(ExamAdminAssignment.admin_id == users_by_username[username].id)
        .count()
        for username in ("admin_cs", "admin_eng", "admin_bus")
    }
    assert assignments_by_admin == {
        "admin_cs": 9,
        "admin_eng": 9,
        "admin_bus": 9,
    }

    assigned_session_ids = {assignment.exam_session_id for assignment in admin_assignments}
    assert assigned_session_ids == {session.id for session in sessions}
    assert {session.created_by for session in sessions} == {
        users_by_username["admin_cs"].id,
        users_by_username["admin_eng"].id,
        users_by_username["admin_bus"].id,
    }


def test_college_seed_keeps_standalone_admin_as_only_super_admin(db_session):
    seed_college(db_session)

    users = db_session.query(User).all()
    users_by_username = {user.username: user for user in users}

    assert [user.username for user in users if user.role == "super_admin"] == ["admin"]
    assert users_by_username["admin"].role == "super_admin"
    assert all(
        user.role == "invigilator"
        for username, user in users_by_username.items()
        if username != "admin"
    )
    assert db_session.query(ExamAdminAssignment).count() == 0
