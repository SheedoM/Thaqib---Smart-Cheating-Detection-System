import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.thaqib.api.dependencies import RequireRole
from src.thaqib.api.ws_manager import manager
from src.thaqib.db.database import get_db
from src.thaqib.db.models.events import Alert
from src.thaqib.db.models.exams import Assignment
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


def _assigned_invigilator_for_alert(db: Session, alert: Alert) -> User | None:
    device = alert.detection_event.device if alert.detection_event else None
    hall_id = device.hall_id if device else None
    query = db.query(Assignment).filter(Assignment.exam_session_id == alert.exam_session_id)
    if hall_id:
        query = query.filter(Assignment.hall_id == hall_id)
    assignment = query.order_by(Assignment.role.asc()).first()
    return assignment.invigilator if assignment else None


def _alert_response(alert: Alert, ptt_target_id: str | None = None) -> dict[str, Any]:
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
        "ptt_target_id": ptt_target_id,
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

    invigilator = _assigned_invigilator_for_alert(db, alert)
    ptt_target_id = None
    if invigilator:
        ptt_target_id = invigilator.ptt_id or invigilator.username or str(invigilator.id)

    db.add(alert)
    db.commit()
    db.refresh(alert)

    if ptt_target_id and alert.detection_event:
        await manager.send_personal_message(
            {
                "type": "incident_card",
                "alert_id": str(alert.id),
                "exam_session_id": str(alert.exam_session_id),
                "event_type": alert.detection_event.event_type,
                "severity": alert.detection_event.severity,
                "timestamp": alert.detection_event.timestamp.isoformat(),
                "student_position": alert.detection_event.student_position,
                "video_clip_path": alert.detection_event.video_clip_path,
                "audio_clip_path": alert.detection_event.audio_clip_path,
                "metadata": alert.detection_event.metadata_json or {},
            },
            ptt_target_id,
        )

    return _alert_response(alert, ptt_target_id)


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
