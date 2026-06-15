from datetime import datetime, timedelta, timezone

import pytest
from starlette.websockets import WebSocketDisconnect

from src.thaqib.api.routes import voice as voice_routes
from src.thaqib.core.security import create_access_token, get_password_hash
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.exams import Assignment, ExamAdminAssignment, ExamSession
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User

VOICE_MAX_BINARY_BYTES = 65_536


class _NoCloseSession:
    """Wrap the test session so the WS handler's `SessionLocal().close()` is a no-op."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, item):
        return getattr(self._session, item)

    def close(self):
        pass


def _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user):
    hall = Hall(institution_id=test_institution.id, name="Voice Hall", capacity=30, status="ready")
    device = Device(
        hall=hall, type="camera", identifier="cam-v",
        position={"label": "Front"}, status="online",
    )
    session = ExamSession(
        institution_id=test_institution.id,
        exam_name="Bio", exam_type="Final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(hours=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active", student_count=30,
    )
    session.halls.append(hall)
    assignment = Assignment(exam_session=session, hall=hall, invigilator=invigilator_user, role="primary")
    admin_assignment = ExamAdminAssignment(
        exam_session=session,
        admin=admin_user,
        assignment_role="lead",
        assigned_by=admin_user.id,
    )
    event = DetectionEvent(
        exam_session=session, device=device, event_type="gaze_alignment", severity="high",
        student_position={"track_id": 5}, timestamp=datetime.now(timezone.utc), confidence_score=0.9,
    )
    alert = Alert(exam_session=session, detection_event=event, alert_type="tier_2", status="pending")
    db_session.add_all([hall, device, session, assignment, admin_assignment, event, alert])
    db_session.commit()
    return hall, alert


def _voice_headers(username: str, origin: str = "http://localhost:5173") -> dict[str, str]:
    token = create_access_token(username)
    return {
        "cookie": f"{voice_routes.settings.access_cookie_name}={token}",
        "origin": origin,
    }


def _assert_ws_rejected(client, url: str, headers: dict[str, str] | None = None, code: int = 1008) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(url, headers=headers or {}):
            pass
    assert exc_info.value.code == code


def test_assigned_invigilator_can_join_hall_voice(client, db_session, test_institution, invigilator_user, admin_user, monkeypatch):
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, _ = _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user)

    with client.websocket_connect(
        f"/api/v1/voice/ws/{hall.id}",
        headers=_voice_headers(invigilator_user.username),
    ) as ws:
        first = ws.receive_json()

    assert first["type"] == "presence"


def test_voice_ws_rejects_query_token_auth(client, db_session, test_institution, invigilator_user, admin_user, monkeypatch):
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, _ = _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user)
    token = create_access_token(invigilator_user.username)

    _assert_ws_rejected(
        client,
        f"/api/v1/voice/ws/{hall.id}?access_token={token}",
        headers={"origin": "http://localhost:5173"},
    )


def test_voice_ws_rejects_untrusted_origin(client, db_session, test_institution, invigilator_user, admin_user, monkeypatch):
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, _ = _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user)

    _assert_ws_rejected(
        client,
        f"/api/v1/voice/ws/{hall.id}",
        headers=_voice_headers(invigilator_user.username, origin="https://evil.example"),
    )


def test_voice_ws_rejects_unassigned_invigilator(client, db_session, test_institution, invigilator_user, admin_user, monkeypatch):
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, _ = _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user)
    other = User(
        institution_id=test_institution.id,
        username="voice_unassigned",
        password_hash=get_password_hash("securepassword"),
        full_name="Unassigned Invigilator",
        email="voice-unassigned@test.com",
        role="invigilator",
        status="active",
    )
    db_session.add(other)
    db_session.commit()

    _assert_ws_rejected(
        client,
        f"/api/v1/voice/ws/{hall.id}",
        headers=_voice_headers(other.username),
    )


def test_voice_ws_rejects_cross_tenant_admin(client, db_session, college_a_admin_user, college_b_hall, monkeypatch):
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))

    _assert_ws_rejected(
        client,
        f"/api/v1/voice/ws/{college_b_hall.id}",
        headers=_voice_headers(college_a_admin_user.username),
    )


def test_voice_ws_rejects_oversized_binary_frame(client, db_session, test_institution, invigilator_user, admin_user, monkeypatch):
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, _ = _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user)

    with client.websocket_connect(
        f"/api/v1/voice/ws/{hall.id}",
        headers=_voice_headers(invigilator_user.username),
    ) as ws:
        first = ws.receive_json()
        assert first["type"] == "presence"
        ws.send_bytes(b"x" * (VOICE_MAX_BINARY_BYTES + 1))
        ws.send_json({"type": "ping"})
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == 1009


def test_confirming_alert_pushes_incident_card_to_hall_voice(
    client, db_session, test_institution, invigilator_user, admin_user, admin_token_headers, monkeypatch
):
    # The WS handler authenticates via its own SessionLocal(); point it at the test session.
    monkeypatch.setattr(voice_routes, "SessionLocal", lambda: _NoCloseSession(db_session))
    hall, alert = _seed_alert_with_hall(db_session, test_institution, invigilator_user, admin_user)

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
