"""
Invigilator live-feed access + hall-scoped alert review.

Covers the gap fixed in this change: invigilators can stream the cameras of the
hall they are assigned to, see only that hall's alerts, review the saved
clip/snapshot, and confirm/cancel — all scoped so they cannot reach another
hall's footage.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.thaqib.api.routes import stream
from src.thaqib.api.routes.stream import _invigilator_can_access_device
from src.thaqib.core.security import get_password_hash
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.exams import Assignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User


def _login(client, username, password="securepassword"):
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}


@pytest.fixture
def two_hall_setup(db_session, test_institution):
    """Two halls, each with a camera, both linked to one session. Invigilator A
    monitors hall A, invigilator B monitors hall B. Each hall has one alert."""
    invig_a = User(
        institution_id=test_institution.id, username="invig_a",
        password_hash=get_password_hash("securepassword"),
        full_name="Invig A", email="invig_a@test.com", role="invigilator",
    )
    invig_b = User(
        institution_id=test_institution.id, username="invig_b",
        password_hash=get_password_hash("securepassword"),
        full_name="Invig B", email="invig_b@test.com", role="invigilator",
    )
    hall_a = Hall(institution_id=test_institution.id, name="Hall A", capacity=30, status="ready")
    hall_b = Hall(institution_id=test_institution.id, name="Hall B", capacity=30, status="ready")
    cam_a = Device(hall=hall_a, type="camera", identifier="cam-a", position={"label": "Front A"}, stream_url="0")
    cam_b = Device(hall=hall_b, type="camera", identifier="cam-b", position={"label": "Front B"}, stream_url="0")

    session = ExamSession(
        exam_name="Final", exam_type="final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(minutes=5),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=2),
        status="active", student_count=30,
        actual_start=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    session.halls = [hall_a, hall_b]
    assign_a = Assignment(
        exam_session=session, hall=hall_a, invigilator=invig_a, role="primary",
        monitoring_started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    assign_b = Assignment(
        exam_session=session, hall=hall_b, invigilator=invig_b, role="primary",
        monitoring_started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )

    db_session.add_all([invig_a, invig_b, hall_a, hall_b, cam_a, cam_b, session, assign_a, assign_b])
    db_session.flush()

    def _make_alert(cam, hall, snapshot=None, clip=None):
        event = DetectionEvent(
            exam_session_id=session.id, device_id=cam.id,
            event_type="غش من الجار", severity="high",
            student_position={"track_id": 7, "looking_at": 9},
            timestamp=datetime.now(timezone.utc),
            video_clip_path=clip,
            metadata_json={"snapshot_file": snapshot, "camera_name": "Front", "hall_name": hall.name},
        )
        alert = Alert(exam_session_id=session.id, detection_event=event, alert_type="tier_2", status="pending")
        db_session.add(alert)
        db_session.flush()
        return alert

    alert_a = _make_alert(cam_a, hall_a)
    alert_b = _make_alert(cam_b, hall_b)
    db_session.commit()

    return {
        "session": session, "hall_a": hall_a, "hall_b": hall_b,
        "cam_a": cam_a, "cam_b": cam_b, "invig_a": invig_a, "invig_b": invig_b,
        "alert_a": alert_a, "alert_b": alert_b,
    }


def test_invigilator_can_access_device_scoped_to_hall(db_session, two_hall_setup):
    s = two_hall_setup
    assert _invigilator_can_access_device(db_session, s["invig_a"], str(s["cam_a"].id)) is True
    # Invigilator A is NOT assigned to hall B's camera.
    assert _invigilator_can_access_device(db_session, s["invig_a"], str(s["cam_b"].id)) is False
    # Garbage id is rejected, not crashed.
    assert _invigilator_can_access_device(db_session, s["invig_a"], "not-a-uuid") is False


def test_status_alerts_are_hall_scoped(client, two_hall_setup):
    s = two_hall_setup
    _login(client, "invig_a")
    resp = client.get(f"/api/sessions/{s['session'].id}/halls/{s['hall_a'].id}/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    alert_ids = {a["id"] for a in body["alerts"]}
    assert str(s["alert_a"].id) in alert_ids
    assert str(s["alert_b"].id) not in alert_ids  # hall B's alert must not leak
    assert body["stats"]["active_alerts"] == 1


def test_invigilator_confirm_and_claim(client, db_session, two_hall_setup):
    s = two_hall_setup
    headers = _login(client, "invig_a")
    base = f"/api/sessions/{s['session'].id}/halls/{s['hall_a'].id}/alerts/{s['alert_a'].id}"

    claim = client.post(f"{base}/claim", headers=headers)
    assert claim.status_code == 200
    assert claim.json()["status"] == "claimed"

    confirm = client.post(f"{base}/confirm", headers=headers)
    assert confirm.status_code == 200
    db_session.refresh(s["alert_a"])
    assert s["alert_a"].status == "confirmed"
    assert s["alert_a"].confirmed_by == s["invig_a"].id


def test_invigilator_cannot_review_other_hall_alert(client, two_hall_setup):
    s = two_hall_setup
    headers = _login(client, "invig_b")  # B is not assigned to hall A
    # B tries to reach hall A's alert clip.
    resp = client.get(
        f"/api/sessions/{s['session'].id}/halls/{s['hall_a'].id}/alerts/{s['alert_a'].id}/clip"
    )
    assert resp.status_code == 403


def test_clip_missing_file_returns_404(client, two_hall_setup):
    s = two_hall_setup
    _login(client, "invig_a")
    # alert_a has no video_clip_path → 404 (file not available)
    resp = client.get(
        f"/api/sessions/{s['session'].id}/halls/{s['hall_a'].id}/alerts/{s['alert_a'].id}/clip"
    )
    assert resp.status_code == 404


def test_snapshot_served_for_owner(client, db_session, two_hall_setup, tmp_path):
    s = two_hall_setup
    # Write a real snapshot under the alerts dir and point the event at it.
    rel = f"test_{uuid.uuid4().hex}/snap.jpg"
    snap_path = stream.ALERTS_DIR / rel
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_bytes(b"\xff\xd8\xff\xe0jpegbytes")
    try:
        event = s["alert_a"].detection_event
        event.metadata_json = {**(event.metadata_json or {}), "snapshot_file": rel}
        db_session.add(event)
        db_session.commit()

        _login(client, "invig_a")
        resp = client.get(
            f"/api/sessions/{s['session'].id}/halls/{s['hall_a'].id}/alerts/{s['alert_a'].id}/snapshot"
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
    finally:
        snap_path.unlink(missing_ok=True)
        try:
            snap_path.parent.rmdir()
        except OSError:
            pass
