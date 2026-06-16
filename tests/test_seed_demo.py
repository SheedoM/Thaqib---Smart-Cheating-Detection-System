from pathlib import Path

from seed_demo import seed_college, seed_university
from src.thaqib.db.models.exams import ExamAdminAssignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User


def test_legacy_scripts_seed_demo_is_removed():
    assert not Path("scripts/seed_demo.py").exists()


def test_college_seed_uses_simulator_ids_urls_and_mic_placements(db_session):
    seed_college(db_session)

    hall = db_session.query(Hall).filter(Hall.name == "قاعة 101").one()
    devices = db_session.query(Device).filter(Device.hall_id == hall.id).all()
    by_identifier = {device.identifier: device for device in devices}

    assert by_identifier["hall101_cam_front"].stream_url == (
        "http://localhost:8000/camera/hall101_cam_front/feed"
    )
    assert by_identifier["hall101_cam_back"].stream_url == (
        "http://localhost:8000/camera/hall101_cam_back/feed"
    )
    assert by_identifier["hall101_cam_side"].stream_url == (
        "http://localhost:8000/camera/hall101_cam_side/feed"
    )
    assert by_identifier["hall101_mic_front"].stream_url == (
        "http://localhost:8000/mic/hall101_mic_front/feed"
    )
    assert by_identifier["hall101_mic_front"].position["placements"] == [
        {"camera_id": "hall101_cam_front", "norm_pos": [0.5, 0.5]},
        {"camera_id": "hall101_cam_back", "norm_pos": [0.5, 0.5]},
        {"camera_id": "hall101_cam_side", "norm_pos": [0.5, 0.5]},
    ]


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
