from datetime import datetime, timedelta, timezone

from src.thaqib.api.routes import voice as voice_routes
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.exams import Assignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall


class _NoCloseSession:
    """Wrap the test session so the WS handler's `SessionLocal().close()` is a no-op."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, item):
        return getattr(self._session, item)

    def close(self):
        pass


def _seed_alert_with_hall(db_session, test_institution, invigilator_user):
    hall = Hall(institution_id=test_institution.id, name="Voice Hall", capacity=30, status="ready")
    device = Device(
        hall=hall, type="camera", identifier="cam-v",
        position={"label": "Front"}, status="online",
    )
    session = ExamSession(
        exam_name="Bio", exam_type="Final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(hours=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active", student_count=30,
    )
    session.halls.append(hall)
    assignment = Assignment(exam_session=session, hall=hall, invigilator=invigilator_user, role="primary")
    event = DetectionEvent(
        exam_session=session, device=device, event_type="gaze_alignment", severity="high",
        student_position={"track_id": 5}, timestamp=datetime.now(timezone.utc), confidence_score=0.9,
    )
    alert = Alert(exam_session=session, detection_event=event, alert_type="tier_2", status="pending")
    db_session.add_all([hall, device, session, assignment, event, alert])
    db_session.commit()
    return hall, alert


def test_confirming_alert_pushes_incident_card_to_hall_voice(
    client, db_session, test_institution, invigilator_user, admin_token_headers, monkeypatch
):
    # The WS handler authenticates via its own SessionLocal(); point it at the test session.
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, alert = _seed_alert_with_hall(db_session, test_institution, invigilator_user)

    with client.websocket_connect(f"/api/v1/voice/ws/{hall.id}") as ws:
        first = ws.receive_json()  # presence frame on join
        assert first["type"] == "presence"

        resp = client.post(f"/api/alerts/{alert.id}/confirm", headers=admin_token_headers)
        assert resp.status_code == 200

        msg = ws.receive_json()
        assert msg["type"] == "incident_card"
        assert msg["alert_id"] == str(alert.id)
        assert msg["event_type"] == "gaze_alignment"
        assert msg["severity"] == "high"
