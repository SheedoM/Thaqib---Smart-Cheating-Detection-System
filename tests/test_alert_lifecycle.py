from datetime import datetime, timedelta, timezone

from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.exams import Assignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall


def _seed_alert(db_session, test_institution, invigilator_user):
    hall = Hall(
        institution_id=test_institution.id,
        name="Hall A",
        capacity=30,
        status="ready",
    )
    device = Device(
        hall=hall,
        type="camera",
        identifier="cam-a",
        position={"label": "Front camera"},
        status="online",
    )
    session = ExamSession(
        exam_name="Physics",
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
    event = DetectionEvent(
        exam_session=session,
        device=device,
        event_type="gaze_alignment",
        severity="high",
        student_position={"track_id": 12, "looking_at": 8},
        timestamp=datetime.now(timezone.utc),
        confidence_score=0.91,
        video_clip_path="20260528/hall-a/clip.mp4",
        metadata_json={"snapshot_file": "20260528/hall-a/snapshot.jpg"},
    )
    alert = Alert(
        exam_session=session,
        detection_event=event,
        alert_type="tier_2",
        status="pending",
    )
    db_session.add_all([hall, device, session, assignment, event, alert])
    db_session.commit()
    return alert


def test_confirm_alert_records_reviewer_and_report_status(client, db_session, test_institution, invigilator_user, admin_user, admin_token_headers):
    alert = _seed_alert(db_session, test_institution, invigilator_user)

    response = client.post(f"/api/alerts/{alert.id}/confirm", headers=admin_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"
    assert data["confirmed_by"] == str(admin_user.id)
    assert data["ptt_target_id"] == invigilator_user.username

    report = client.get(f"/api/sessions/{alert.exam_session_id}/report").json()
    assert report["kpis"]["total_events"] == 1
    assert report["kpis"]["confirmed_incidents"] == 1
    assert report["kpis"]["cancelled_incidents"] == 0
    assert report["timeline"][0]["alert_status"] == "confirmed"
    assert report["timeline"][0]["video_clip_path"] == "20260528/hall-a/clip.mp4"
    assert report["timeline"][0]["snapshot_file"] == "20260528/hall-a/snapshot.jpg"


def test_cancel_alert_keeps_evidence_in_report(client, db_session, test_institution, invigilator_user, admin_token_headers):
    alert = _seed_alert(db_session, test_institution, invigilator_user)

    response = client.post(
        f"/api/alerts/{alert.id}/cancel",
        headers=admin_token_headers,
        json={"notes": "Reviewed clip; no cheating."},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    report = client.get(f"/api/sessions/{alert.exam_session_id}/report").json()
    assert report["kpis"]["confirmed_incidents"] == 0
    assert report["kpis"]["cancelled_incidents"] == 1
    assert report["timeline"][0]["alert_status"] == "cancelled"
    assert report["timeline"][0]["resolution_notes"] == "Reviewed clip; no cheating."
