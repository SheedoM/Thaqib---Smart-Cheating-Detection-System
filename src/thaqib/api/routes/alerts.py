import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.thaqib.api.dependencies import RequireRole
from src.thaqib.api.routes import voice
from src.thaqib.db.database import get_db
from src.thaqib.db.models.events import Alert
from src.thaqib.db.models.users import User

router = APIRouter()
require_admin = RequireRole(["admin"])


class AlertReviewRequest(BaseModel):
    notes: Optional[str] = None


def _alert_or_404(db: Session, alert_id: uuid.UUID) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


def _alert_response(alert: Alert) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "status": alert.status,
        "exam_session_id": str(alert.exam_session_id),
        "detection_event_id": str(alert.detection_event_id) if alert.detection_event_id else None,
        "confirmed_by": str(alert.confirmed_by) if alert.confirmed_by else None,
        "confirmed_at": alert.confirmed_at.isoformat() if alert.confirmed_at else None,
        "cancelled_by": str(alert.cancelled_by) if alert.cancelled_by else None,
        "cancelled_at": alert.cancelled_at.isoformat() if alert.cancelled_at else None,
        "resolution_notes": alert.resolution_notes,
    }


@router.post("/{alert_id}/confirm")
async def confirm_alert(
    alert_id: uuid.UUID,
    payload: AlertReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    alert = _alert_or_404(db, alert_id)
    now = datetime.now(timezone.utc)
    alert.status = "confirmed"
    alert.confirmed_by = current_user.id
    alert.confirmed_at = now
    alert.cancelled_by = None
    alert.cancelled_at = None
    if payload and payload.notes:
        alert.resolution_notes = payload.notes

    db.add(alert)
    db.commit()
    db.refresh(alert)

    # Notify the hall's voice channel so the invigilator's device shows the
    # confirmed incident (replaces the old PTT incident-card push).
    event = alert.detection_event
    device = event.device if event else None
    hall_id = device.hall_id if device else None
    if event and hall_id is not None:
        await voice.notify_hall(
            str(hall_id),
            {
                "type": "incident_card",
                "alert_id": str(alert.id),
                "exam_session_id": str(alert.exam_session_id),
                "event_type": event.event_type,
                "severity": event.severity,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "student_position": event.student_position,
                "video_clip_path": event.video_clip_path,
                "audio_clip_path": event.audio_clip_path,
                "metadata": event.metadata_json or {},
            },
        )

    return _alert_response(alert)


@router.post("/{alert_id}/cancel")
def cancel_alert(
    alert_id: uuid.UUID,
    payload: AlertReviewRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    alert = _alert_or_404(db, alert_id)
    now = datetime.now(timezone.utc)
    alert.status = "cancelled"
    alert.cancelled_by = current_user.id
    alert.cancelled_at = now
    alert.resolved_at = now
    alert.resolution_notes = payload.notes if payload and payload.notes else alert.resolution_notes

    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _alert_response(alert)
