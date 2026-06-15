from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.thaqib.db.models.audit import AuditLog
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.exams import Assignment, ExamAdminAssignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User
from src.thaqib.core.security import get_password_hash


def _plus_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def _seed_alert(db_session, test_institution, invigilator_user, admin_user):
    hall = Hall(
        institution_id=test_institution.id,
        name="Retention Hall",
        capacity=30,
        status="ready",
    )
    device = Device(
        hall=hall,
        type="camera",
        identifier="retention-cam",
        position={"label": "Front camera"},
        status="online",
    )
    session = ExamSession(
        institution_id=test_institution.id,
        exam_name="Retention Exam",
        exam_type="Final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(hours=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
        student_count=30,
    )
    session.halls.append(hall)
    assignment = Assignment(
        exam_session=session,
        hall=hall,
        invigilator=invigilator_user,
        role="primary",
    )
    admin_assignment = ExamAdminAssignment(
        exam_session=session,
        admin=admin_user,
        assignment_role="lead",
        assigned_by=admin_user.id,
    )
    event = DetectionEvent(
        exam_session=session,
        device=device,
        event_type="gaze_alignment",
        severity="high",
        student_position={"track_id": 12, "looking_at": 8},
        timestamp=datetime.now(timezone.utc),
        confidence_score=0.91,
        video_clip_path="20260616/retention-hall/clips/clip.mp4",
        metadata_json={"snapshot_file": "20260616/retention-hall/snapshots/snapshot.jpg"},
    )
    alert = Alert(
        exam_session=session,
        detection_event=event,
        alert_type="tier_2",
        status="pending",
    )
    db_session.add_all([hall, device, session, assignment, admin_assignment, event, alert])
    db_session.commit()
    return alert


def test_confirmed_alert_keeps_evidence_for_three_years(
    client,
    db_session,
    test_institution,
    invigilator_user,
    admin_user,
    admin_token_headers,
):
    alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)

    response = client.post(f"/api/alerts/{alert.id}/confirm", headers=admin_token_headers)

    assert response.status_code == 200
    db_session.refresh(alert)
    assert alert.status == "confirmed"
    assert alert.evidence_retention_until == _plus_years(alert.confirmed_at, 3)
    assert response.json()["evidence_retention_until"] == alert.evidence_retention_until.isoformat()


def test_cancelled_alert_keeps_evidence_for_thirty_days(
    client,
    db_session,
    test_institution,
    invigilator_user,
    admin_user,
    admin_token_headers,
):
    alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)

    response = client.post(f"/api/alerts/{alert.id}/cancel", headers=admin_token_headers)

    assert response.status_code == 200
    db_session.refresh(alert)
    assert alert.status == "cancelled"
    assert alert.evidence_retention_until == alert.cancelled_at + timedelta(days=30)
    assert response.json()["evidence_retention_until"] == alert.evidence_retention_until.isoformat()


def test_assigned_admin_can_place_and_release_legal_hold(
    client,
    db_session,
    test_institution,
    invigilator_user,
    admin_user,
    admin_token_headers,
):
    alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)

    place = client.post(
        f"/api/alerts/{alert.id}/legal-hold",
        headers=admin_token_headers,
        json={"reason": "Student appeal filed."},
    )
    release = client.delete(f"/api/alerts/{alert.id}/legal-hold", headers=admin_token_headers)

    assert place.status_code == 200
    assert place.json()["legal_hold"] is True
    assert release.status_code == 200
    assert release.json()["legal_hold"] is False

    db_session.refresh(alert)
    assert alert.legal_hold is False
    actions = [row.action_type for row in db_session.query(AuditLog).all()]
    assert "evidence_legal_hold_placed" in actions
    assert "evidence_legal_hold_released" in actions


def test_super_admin_can_place_legal_hold_within_institution_scope(
    client,
    db_session,
    test_institution,
    invigilator_user,
    admin_user,
    super_admin_token_headers,
):
    alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)

    response = client.post(
        f"/api/alerts/{alert.id}/legal-hold",
        headers=super_admin_token_headers,
        json={"reason": "Registrar review."},
    )

    assert response.status_code == 200
    assert response.json()["legal_hold"] is True


def test_unassigned_admin_cannot_place_legal_hold(
    client,
    db_session,
    test_institution,
    invigilator_user,
    admin_user,
):
    alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)
    unassigned = User(
        institution_id=test_institution.id,
        username="unassigned_retention_admin",
        password_hash=get_password_hash("securepassword"),
        full_name="Unassigned Retention Admin",
        email="unassigned-retention@test.com",
        role="admin",
        status="active",
    )
    db_session.add(unassigned)
    db_session.commit()
    login = client.post(
        "/api/auth/login",
        data={"username": unassigned.username, "password": "securepassword"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    response = client.post(
        f"/api/alerts/{alert.id}/legal-hold",
        headers=headers,
        json={"reason": "Should be denied."},
    )

    assert response.status_code == 403


def test_retention_purge_deletes_expired_evidence_but_skips_legal_hold(
    db_session,
    tmp_path,
    test_institution,
    invigilator_user,
    admin_user,
):
    from src.thaqib.services.evidence_retention import purge_expired_alert_evidence

    alerts_dir = tmp_path / "alerts"
    expired_alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)
    held_alert = _seed_alert(db_session, test_institution, invigilator_user, admin_user)

    for alert, prefix in [(expired_alert, "expired"), (held_alert, "held")]:
        clip = Path(prefix) / "clips" / "clip.mp4"
        snapshot = Path(prefix) / "snapshots" / "snapshot.jpg"
        (alerts_dir / clip).parent.mkdir(parents=True, exist_ok=True)
        (alerts_dir / snapshot).parent.mkdir(parents=True, exist_ok=True)
        (alerts_dir / clip).write_bytes(b"clip")
        (alerts_dir / snapshot).write_bytes(b"snapshot")
        alert.detection_event.video_clip_path = clip.as_posix()
        alert.detection_event.metadata_json = {"snapshot_file": snapshot.as_posix()}
        alert.status = "cancelled"
        alert.cancelled_at = datetime.now(timezone.utc) - timedelta(days=31)
        alert.evidence_retention_until = datetime.now(timezone.utc) - timedelta(days=1)

    held_alert.legal_hold = True
    db_session.commit()

    result = purge_expired_alert_evidence(
        db_session,
        alerts_dir=alerts_dir,
        now=datetime.now(timezone.utc),
    )

    db_session.refresh(expired_alert)
    db_session.refresh(held_alert)
    assert result.purged_count == 1
    assert str(expired_alert.id) in result.purged_alert_ids
    assert not (alerts_dir / "expired/clips/clip.mp4").exists()
    assert not (alerts_dir / "expired/snapshots/snapshot.jpg").exists()
    assert (alerts_dir / "held/clips/clip.mp4").exists()
    assert expired_alert.detection_event.video_clip_path is None
    assert expired_alert.detection_event.metadata_json.get("snapshot_file") is None
    assert expired_alert.evidence_purged_at is not None
