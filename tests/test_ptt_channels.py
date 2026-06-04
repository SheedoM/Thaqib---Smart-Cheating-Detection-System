import uuid
from datetime import datetime, timedelta, timezone

from src.thaqib.api.ws_manager import manager
from src.thaqib.db.models.exams import Assignment, ExamSession
from src.thaqib.db.models.infrastructure import Hall, HallVoiceChannel
from src.thaqib.db.models.ptt import PttClip


def test_create_hall_creates_default_voice_channel(client, db_session, test_institution, admin_token_headers):
    response = client.post(
        "/api/halls/",
        headers=admin_token_headers,
        json={
            "institution_id": str(test_institution.id),
            "name": "Hall Voice",
            "capacity": 40,
            "status": "ready",
        },
    )

    assert response.status_code == 201
    hall_id = response.json()["id"]

    channel = (
        db_session.query(HallVoiceChannel)
        .filter(HallVoiceChannel.hall_id == uuid.UUID(hall_id))
        .one()
    )
    assert channel.channel_key == f"hall:{hall_id}"
    assert channel.status == "active"


def test_ptt_hall_status_reports_control_and_invigilator_presence(
    client,
    db_session,
    test_institution,
    admin_token_headers,
):
    hall = Hall(institution_id=test_institution.id, name="Hall Presence", capacity=35, status="ready")
    db_session.add(hall)
    db_session.commit()
    db_session.refresh(hall)

    channel = HallVoiceChannel(hall_id=hall.id, channel_key=f"hall:{hall.id}", status="active")
    db_session.add(channel)
    db_session.commit()

    original = manager.channel_connections.copy()
    try:
        manager.channel_connections.clear()
        manager.channel_connections[str(channel.id)] = {
            "admin_test": {
                "websocket": object(),
                "role": "admin",
                "mic_state": "ready",
                "is_transmitting": False,
                "full_name": "Admin Test",
            },
            "invig_test": {
                "websocket": object(),
                "role": "invigilator",
                "mic_state": "blocked",
                "is_transmitting": True,
                "full_name": "Invigilator Test",
            },
        }

        response = client.get(
            f"/api/v1/ptt/halls/{hall.id}/status",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["hall_id"] == str(hall.id)
        assert data["channel_id"] == str(channel.id)
        assert data["control_connected"] is True
        assert data["invigilator_connected"] is True
        assert data["control_mic_state"] == "ready"
        assert data["invigilator_mic_state"] == "blocked"
        assert data["is_transmitting"] is True
    finally:
        manager.channel_connections.clear()
        manager.channel_connections.update(original)


def test_ptt_clip_log_appears_in_session_report(
    client,
    db_session,
    test_institution,
    invigilator_user,
    admin_user,
    admin_token_headers,
):
    hall = Hall(institution_id=test_institution.id, name="Hall Report", capacity=35, status="ready")
    channel = HallVoiceChannel(hall=hall, channel_key="hall:report", status="active")
    session = ExamSession(
        exam_name="Chemistry",
        exam_type="Final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(hours=1),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
        student_count=35,
    )
    session.halls.append(hall)
    assignment = Assignment(
        exam_session=session,
        hall=hall,
        invigilator=invigilator_user,
        role="primary",
        monitoring_started_at=datetime.now(timezone.utc),
    )
    clip = PttClip(
        exam_session=session,
        hall=hall,
        channel=channel,
        speaker=admin_user,
        speaker_role="admin",
        speaker_name="Admin Test",
        clip_type="normal",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc) + timedelta(seconds=3),
        duration_ms=3000,
        audio_file_path="uploads/ptt_clips/clip.wav",
        metadata_json={"sample_rate": 16000},
    )
    db_session.add_all([hall, channel, session, assignment, clip])
    db_session.commit()

    response = client.get(f"/api/sessions/{session.id}/report", headers=admin_token_headers)

    assert response.status_code == 200
    clips = response.json()["ptt_clips"]
    assert clips == [
        {
            "id": str(clip.id),
            "hall_id": str(hall.id),
            "hall_name": "Hall Report",
            "speaker_id": str(admin_user.id),
            "speaker_name": "Admin Test",
            "speaker_role": "admin",
            "clip_type": "normal",
            "alert_id": None,
            "started_at": clip.started_at.isoformat(),
            "ended_at": clip.ended_at.isoformat(),
            "duration_ms": 3000,
            "audio_file_path": "uploads/ptt_clips/clip.wav",
        }
    ]
