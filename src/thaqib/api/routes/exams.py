import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Any, Optional
import cv2
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from src.thaqib.db.database import get_db
from src.thaqib.db.models.exams import ExamAdminAssignment, ExamSession, Assignment
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.schemas.exams import (
    ExamSessionCreate, ExamSessionResponse, ExamSessionUpdate, 
    AssignmentCreate, AssignmentResponse, AssignmentDetailedResponse,
    ExamAdminAssignmentCreate, ExamAdminAssignmentResponse,
)
from src.thaqib.api.dependencies import RequireRole, get_current_user, get_scope
from src.thaqib.core.limiter import limiter
from src.thaqib.api.routes import stream, voice

router = APIRouter()
require_admin = RequireRole(["admin"])
require_admin_or_super_admin = RequireRole(["admin", "super_admin"])
require_hall_operator = RequireRole(["invigilator", "admin"])


def _parse_camera_source(source: str) -> int | str:
    try:
        return int(source)
    except (TypeError, ValueError):
        return source


def _camera_readiness(device: Device) -> dict[str, Any]:
    source = (device.stream_url or "").strip()
    if not source:
        return {
            "id": str(device.id),
            "type": device.type,
            "identifier": device.identifier,
            "name": (device.position or {}).get("label") or device.identifier,
            "status": "failed",
            "message": "Camera stream URL is not configured.",
        }

    capture = cv2.VideoCapture(_parse_camera_source(source))
    try:
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1500)
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1500)
    except Exception:
        pass

    try:
        ok, _ = capture.read() if capture.isOpened() else (False, None)
    finally:
        capture.release()

    if not ok:
        return {
            "id": str(device.id),
            "type": device.type,
            "identifier": device.identifier,
            "name": (device.position or {}).get("label") or device.identifier,
            "status": "failed",
            "message": "Camera stream could not be opened or read.",
        }

    return {
        "id": str(device.id),
        "type": device.type,
        "identifier": device.identifier,
        "name": (device.position or {}).get("label") or device.identifier,
        "status": "passed",
        "message": "Camera stream is reachable.",
    }


def _microphone_readiness(device: Device) -> dict[str, Any]:
    healthy = device.status in {"online", "active", "ready", "running"}
    return {
        "id": str(device.id),
        "type": device.type,
        "identifier": device.identifier,
        "name": (device.position or {}).get("label") or device.identifier,
        "status": "passed" if healthy else "failed",
        "message": "Microphone is marked online." if healthy else f"Microphone status is {device.status or 'unknown'}.",
    }


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_session_hall_and_assignment(
    db: Session,
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    current_user: User,
) -> tuple[ExamSession, Hall, Assignment | None]:
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")

    hall = (
        db.query(Hall)
        .filter(Hall.id == hall_id, Hall.deleted_at.is_(None))
        .options(selectinload(Hall.devices))
        .first()
    )

    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id,
    ).first()

    hall_linked = any(h.id == hall_id for h in session.halls)
    if not hall or (not hall_linked and assignment is None):
        raise HTTPException(status_code=404, detail="Hall is not linked to this exam session")

    if current_user.role == "admin":
        _require_admin_assigned_to_exam(db, session_id, current_user)
    else:
        if not assignment or assignment.invigilator_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not assigned to monitor this hall")

    return session, hall, assignment


def _admin_assignment(
    db: Session,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ExamAdminAssignment | None:
    return db.query(ExamAdminAssignment).filter(
        ExamAdminAssignment.exam_session_id == session_id,
        ExamAdminAssignment.admin_id == user_id,
    ).first()


def _require_admin_assigned_to_exam(
    db: Session,
    session_id: uuid.UUID,
    current_user: User,
) -> ExamAdminAssignment:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Operation requires an assigned admin")
    assignment = _admin_assignment(db, session_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=403, detail="Admin is not assigned to this exam")
    return assignment


def _require_exam_observer(
    db: Session,
    session_id: uuid.UUID,
    current_user: User,
) -> None:
    if current_user.role == "super_admin":
        return
    _require_admin_assigned_to_exam(db, session_id, current_user)

@router.get("/my", response_model=List[AssignmentDetailedResponse])
def get_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get assignments for the currently logged-in invigilator.
    """
    assignments = db.query(Assignment).filter(Assignment.invigilator_id == current_user.id).all()
    
    # Enrich with names
    results = []
    for a in assignments:
        results.append({
            "id": a.id,
            "invigilator_id": a.invigilator_id,
            "hall_id": a.hall_id,
            "role": a.role,
            "exam_session_id": a.exam_session_id,
            "monitoring_started_at": a.monitoring_started_at,
            "monitoring_ended_at": a.monitoring_ended_at,
            "exam_name": a.exam_session.exam_name,
            "hall_name": a.hall.name,
            "scheduled_start": a.exam_session.scheduled_start,
            "scheduled_end": a.exam_session.scheduled_end
        })
    return results

@router.post("/{session_id}/halls/{hall_id}/monitoring/start")
def start_monitoring(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator)
) -> Any:
    """
    Start monitoring for a specific hall in an exam session.
    Only the assigned invigilator or an admin can start monitoring.
    """
    # Verify assignment
    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="No assignment found for this hall and session")
        
    # Check permission
    if current_user.role == "admin":
        _require_admin_assigned_to_exam(db, session_id, current_user)
    elif assignment.invigilator_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not assigned to monitor this hall")
        
    stream.start_hall_monitoring(hall_id, session_id, db)
    return {"status": "monitoring started"}


@router.get("/{session_id}/halls/{hall_id}/readiness")
def get_hall_readiness(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator)
) -> Any:
    """
    Check every configured camera and microphone before a hall starts monitoring.
    Failed checks are warnings for the UI; start remains allowed by policy.
    """
    session, hall, _ = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    active_devices = [device for device in hall.devices if device.deleted_at is None]

    results = []
    for device in active_devices:
        if device.type == "camera":
            results.append(_camera_readiness(device))
        elif device.type == "microphone":
            results.append(_microphone_readiness(device))

    camera_count = sum(1 for device in active_devices if device.type == "camera")
    mic_count = sum(1 for device in active_devices if device.type == "microphone")
    if camera_count == 0:
        results.append({
            "id": "missing-camera",
            "type": "camera",
            "identifier": "missing-camera",
            "name": "Camera",
            "status": "failed",
            "message": "No cameras are registered for this hall.",
        })
    if mic_count == 0:
        results.append({
            "id": "missing-microphone",
            "type": "microphone",
            "identifier": "missing-microphone",
            "name": "Microphone",
            "status": "failed",
            "message": "No microphones are registered for this hall.",
        })

    failed_count = sum(1 for result in results if result["status"] != "passed")
    return {
        "session_id": str(session.id),
        "hall_id": str(hall.id),
        "hall_name": hall.name,
        "exam_name": session.exam_name,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": "passed" if failed_count == 0 else "warning",
        "failed_count": failed_count,
        "devices": results,
    }

@router.get("/{session_id}/halls/{hall_id}/feeds")
def get_hall_feeds(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator)
) -> Any:
    """
    Return active camera feed paths for a hall so the invigilator can view streams.
    Invigilators can only access halls they are assigned to.
    """
    session, hall, assignment = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    
    active_devices = [d for d in hall.devices if d.deleted_at is None and d.type == "camera"]
    feeds = [
        {
            "device_id": str(d.id),
            "name": (d.position or {}).get("label") or d.identifier,
            "feed_path": f"/api/stream/feed/{d.id}",
            "source_configured": bool((d.stream_url or "").strip()),
        }
        for d in active_devices
    ]
    return {"hall_id": str(hall_id), "hall_name": hall.name, "feeds": feeds}


@router.post("/{session_id}/halls/{hall_id}/monitoring/stop")
def stop_monitoring(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator)
) -> Any:
    """
    Stop monitoring for a specific hall in an exam session.
    """
    # Verify assignment
    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="No assignment found for this hall and session")
        
    # Check permission
    if current_user.role == "admin":
        _require_admin_assigned_to_exam(db, session_id, current_user)
    elif assignment.invigilator_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not assigned to this hall")
        
    stream.stop_hall_monitoring(hall_id, session_id, db)
    return {"status": "monitoring stopped"}

def _hall_camera_device_ids(hall: Hall) -> list[uuid.UUID]:
    """IDs of the hall's live (non-deleted) camera devices — used to scope alerts."""
    return [d.id for d in hall.devices if d.deleted_at is None and d.type == "camera"]


def _serialize_hall_alert(alert: Alert) -> dict[str, Any]:
    """Shape an Alert (+ its detection event) for the invigilator's review list."""
    event = alert.detection_event
    meta = (event.metadata_json or {}) if event else {}
    pos = (event.student_position or {}) if event else {}
    camera_name = meta.get("camera_name")
    hall_name = meta.get("hall_name")
    location = " - ".join(part for part in (hall_name, camera_name) if part)
    return {
        "id": str(alert.id),
        "event_id": str(event.id) if event else None,
        "type": event.event_type if event else "",
        "event_type": event.event_type if event else "",
        "message": f"{event.event_type} - {event.severity}" if event else "",
        "severity": event.severity if event else None,
        "timestamp": event.timestamp.isoformat() if event and event.timestamp else None,
        "confidence_score": float(event.confidence_score) if event and event.confidence_score else None,
        "status": alert.status,
        "claimed_by": str(alert.claimed_by) if alert.claimed_by else None,
        "camera_name": camera_name,
        "location": location,
        "track_id": pos.get("track_id"),
        "looking_at": pos.get("looking_at"),
        "has_clip": bool(event.video_clip_path) if event else False,
        "has_snapshot": bool(meta.get("snapshot_file")) if event else False,
    }


def _get_hall_alert(db: Session, session_id: uuid.UUID, hall: Hall, alert_id: uuid.UUID) -> Alert:
    """Load an alert and confirm it belongs to this hall (its event's device is a
    camera in this hall). 404 otherwise — this is the scoping gate for review/clips."""
    camera_ids = _hall_camera_device_ids(hall)
    if not camera_ids:
        raise HTTPException(status_code=404, detail="Alert not found for this hall")
    alert = (
        db.query(Alert)
        .join(DetectionEvent, Alert.detection_event_id == DetectionEvent.id)
        .filter(
            Alert.id == alert_id,
            Alert.exam_session_id == session_id,
            DetectionEvent.device_id.in_(camera_ids),
        )
        .options(selectinload(Alert.detection_event))
        .first()
    )
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found for this hall")
    return alert


def _serve_alert_file(rel_path: str | None, media_by_suffix: dict[str, str], default_media: str) -> FileResponse:
    """Serve a stored alert clip/snapshot, guarding against path traversal outside
    the alerts directory."""
    if not rel_path:
        raise HTTPException(status_code=404, detail="File not available")
    filepath = (stream.ALERTS_DIR / Path(rel_path)).resolve()
    if stream._ROOT_ALERTS_DIR not in filepath.parents or not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media = media_by_suffix.get(filepath.suffix.lower(), default_media)
    return FileResponse(str(filepath), media_type=media)


def _hall_alert_review_response(alert: Alert) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "status": alert.status,
        "claimed_by": str(alert.claimed_by) if alert.claimed_by else None,
        "confirmed_by": str(alert.confirmed_by) if alert.confirmed_by else None,
        "cancelled_by": str(alert.cancelled_by) if alert.cancelled_by else None,
    }


@router.get("/{session_id}/halls/{hall_id}/status")
def get_hall_monitoring_status(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator)
) -> Any:
    """
    Get the current monitoring status of a specific hall in a session.
    Alerts are scoped to this hall's cameras, not the whole session.
    """
    session, hall, assignment = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    is_active = assignment.monitoring_started_at is not None and assignment.monitoring_ended_at is None

    camera_ids = _hall_camera_device_ids(hall)
    active_alert_count = 0
    recent_alerts: list[dict[str, Any]] = []
    if camera_ids:
        active_alert_count = (
            db.query(Alert)
            .join(DetectionEvent, Alert.detection_event_id == DetectionEvent.id)
            .filter(
                Alert.exam_session_id == session_id,
                DetectionEvent.device_id.in_(camera_ids),
                Alert.status.in_(["pending", "claimed"]),
            )
            .count()
        )
        alert_rows = (
            db.query(Alert)
            .join(DetectionEvent, Alert.detection_event_id == DetectionEvent.id)
            .filter(
                Alert.exam_session_id == session_id,
                DetectionEvent.device_id.in_(camera_ids),
            )
            .options(selectinload(Alert.detection_event))
            .order_by(DetectionEvent.timestamp.desc())
            .limit(50)
            .all()
        )
        recent_alerts = [_serialize_hall_alert(a) for a in alert_rows]

    return {
        "hall_id": str(hall_id),
        "hall_name": hall.name,
        "exam_name": session.exam_name,
        "is_active": is_active,
        "started_at": assignment.monitoring_started_at,
        "ended_at": assignment.monitoring_ended_at,
        "stats": {
            "student_count": session.student_count or 0,
            "active_alerts": active_alert_count,
        },
        "alerts": recent_alerts,
    }


class HallAlertReviewBody(BaseModel):
    notes: Optional[str] = None


@router.post("/{session_id}/halls/{hall_id}/alerts/{alert_id}/claim")
def claim_hall_alert(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator),
) -> Any:
    """Mark that the invigilator is handling this alert (called when they open it).
    Moves it out of the 'unreviewed' bucket so the control room knows it's covered."""
    session, hall, _ = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    alert = _get_hall_alert(db, session_id, hall, alert_id)
    if alert.claimed_by is None and alert.status == "pending":
        alert.claimed_by = current_user.id
        alert.claimed_at = datetime.now(timezone.utc)
        alert.status = "claimed"
        db.add(alert)
        db.commit()
        db.refresh(alert)
    return _hall_alert_review_response(alert)


@router.post("/{session_id}/halls/{hall_id}/alerts/{alert_id}/confirm")
async def confirm_hall_alert(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    alert_id: uuid.UUID,
    payload: HallAlertReviewBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator),
) -> Any:
    """Confirm an alert as a real incident. Both the assigned invigilator and an
    assigned admin may confirm. An admin confirmation still pushes an incident card
    to the hall voice channel; an invigilator's confirmation does not (they are
    already on the ground acting on it)."""
    session, hall, _ = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    alert = _get_hall_alert(db, session_id, hall, alert_id)
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

    if current_user.role == "admin":
        event = alert.detection_event
        device = event.device if event else None
        notify_hall_id = device.hall_id if device else None
        if event and notify_hall_id is not None:
            await voice.notify_hall(
                str(notify_hall_id),
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

    return _hall_alert_review_response(alert)


@router.post("/{session_id}/halls/{hall_id}/alerts/{alert_id}/cancel")
def cancel_hall_alert(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    alert_id: uuid.UUID,
    payload: HallAlertReviewBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator),
) -> Any:
    """Dismiss an alert as a false alarm after reviewing the clip."""
    session, hall, _ = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    alert = _get_hall_alert(db, session_id, hall, alert_id)
    now = datetime.now(timezone.utc)
    alert.status = "cancelled"
    alert.cancelled_by = current_user.id
    alert.cancelled_at = now
    alert.resolved_at = now
    if payload and payload.notes:
        alert.resolution_notes = payload.notes
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return _hall_alert_review_response(alert)


@router.get("/{session_id}/halls/{hall_id}/alerts/{alert_id}/clip")
def get_hall_alert_clip(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator),
) -> FileResponse:
    """Serve the saved video clip for an alert in this hall (invigilator review)."""
    session, hall, _ = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    alert = _get_hall_alert(db, session_id, hall, alert_id)
    event = alert.detection_event
    return _serve_alert_file(
        event.video_clip_path if event else None,
        {".mp4": "video/mp4", ".avi": "video/x-msvideo"},
        "video/mp4",
    )


@router.get("/{session_id}/halls/{hall_id}/alerts/{alert_id}/snapshot")
def get_hall_alert_snapshot(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    alert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_hall_operator),
) -> FileResponse:
    """Serve the saved snapshot image for an alert in this hall."""
    session, hall, _ = _get_session_hall_and_assignment(db, session_id, hall_id, current_user)
    alert = _get_hall_alert(db, session_id, hall, alert_id)
    event = alert.detection_event
    snapshot = (event.metadata_json or {}).get("snapshot_file") if event else None
    return _serve_alert_file(
        snapshot,
        {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"},
        "image/jpeg",
    )

def _resolve_halls_and_institution(
    db: Session,
    hall_ids: list[uuid.UUID],
) -> tuple[list[Hall], uuid.UUID]:
    """Fetch halls, validate they all share one institution, return (halls, institution_id)."""
    if not hall_ids:
        raise HTTPException(status_code=400, detail="At least one hall is required.")
    halls = db.query(Hall).filter(Hall.id.in_(hall_ids), Hall.deleted_at.is_(None)).all()
    if len(halls) != len(hall_ids):
        raise HTTPException(status_code=400, detail="One or more halls could not be found.")
    inst_ids = {h.institution_id for h in halls}
    if len(inst_ids) > 1:
        raise HTTPException(status_code=400, detail="All halls must belong to the same institution.")
    return halls, inst_ids.pop()


@router.post("/", response_model=ExamSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_exam_session(
    request: Request,
    session_data: ExamSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    scope = Depends(get_scope),
) -> Any:
    """
    Create a new exam session. Admin only, halls must belong to one accessible institution.
    """
    halls, institution_id = _resolve_halls_and_institution(db, session_data.hall_ids)
    if institution_id not in scope:
        raise HTTPException(status_code=404, detail="One or more halls could not be found.")

    new_session = ExamSession(
        institution_id=institution_id,
        exam_name=session_data.exam_name,
        exam_type=session_data.exam_type,
        scheduled_start=session_data.scheduled_start,
        scheduled_end=session_data.scheduled_end,
        status=session_data.status,
        student_count=session_data.student_count,
        configuration=session_data.configuration,
        created_by=current_user.id,
    )

    new_session.halls = halls

    db.add(new_session)
    db.flush()
    db.add(
        ExamAdminAssignment(
            exam_session_id=new_session.id,
            admin_id=current_user.id,
            assignment_role="lead",
            assigned_by=current_user.id,
        )
    )
    db.commit()
    db.refresh(new_session)
    return new_session

@router.get("/", response_model=List[ExamSessionResponse])
def read_exam_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Retrieve exam sessions scoped to the caller's accessible institutions.
    Admins are further narrowed to their assigned exams.
    """
    query = db.query(ExamSession).filter(ExamSession.institution_id.in_(scope))
    if current_user.role == "admin":
        query = query.join(ExamAdminAssignment).filter(
            ExamAdminAssignment.admin_id == current_user.id
        )
    sessions = query.offset(skip).limit(limit).all()
    return sessions

@router.get("/{session_id}", response_model=ExamSessionResponse)
def read_exam_session(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Get exam session by ID. Returns 404 for out-of-scope sessions.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.institution_id.in_(scope),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _require_exam_observer(db, session_id, current_user)
    return session

@router.put("/{session_id}", response_model=ExamSessionResponse)
@limiter.limit("10/minute")
def update_exam_session(
    request: Request,
    session_id: uuid.UUID,
    session_in: ExamSessionUpdate,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Update an exam session. Assigned admin only.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.institution_id.in_(scope),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _require_admin_assigned_to_exam(db, session_id, current_user)

    update_data = session_in.model_dump(exclude_unset=True)
    hall_ids = update_data.pop("hall_ids", None)
    if hall_ids is not None:
        halls, new_inst_id = _resolve_halls_and_institution(db, hall_ids)
        if new_inst_id not in scope:
            raise HTTPException(status_code=400, detail="One or more halls could not be found.")
        session.institution_id = new_inst_id
        session.halls = halls

    for field, value in update_data.items():
        setattr(session, field, value)

    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.delete("/{session_id}", response_model=ExamSessionResponse)
@limiter.limit("5/minute")
def delete_exam_session(
    request: Request,
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin),
) -> Any:
    """
    Delete an exam session. Assigned admin only.
    """
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.institution_id.in_(scope),
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _require_admin_assigned_to_exam(db, session_id, current_user)
        
    db.delete(session)
    db.commit()
    return session


@router.post(
    "/{session_id}/admins",
    response_model=ExamAdminAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("20/minute")
def assign_exam_admin(
    request: Request,
    session_id: uuid.UUID,
    assignment: ExamAdminAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Any:
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    current_assignment = _require_admin_assigned_to_exam(db, session_id, current_user)
    if current_assignment.assignment_role != "lead":
        raise HTTPException(status_code=403, detail="Only lead admins can assign exam admins")

    user = db.query(User).filter(User.id == assignment.admin_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Admin not found")
    if user.role != "admin":
        raise HTTPException(status_code=400, detail="User must be an admin")

    existing = _admin_assignment(db, session_id, assignment.admin_id)
    if existing:
        raise HTTPException(status_code=400, detail="Admin is already assigned to this exam")

    new_assignment = ExamAdminAssignment(
        exam_session_id=session_id,
        admin_id=assignment.admin_id,
        assignment_role=assignment.assignment_role or "reviewer",
        assigned_by=current_user.id,
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return new_assignment

@router.post("/{session_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def assign_invigilator(
    request: Request,
    session_id: uuid.UUID,
    assignment: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Assign an invigilator to an exam session. Assigned admin only.
    """
    # Verify session
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _require_admin_assigned_to_exam(db, session_id, current_user)
        
    # Verify hall is linked to this session
    hall_linked = any(h.id == assignment.hall_id for h in session.halls)
    if not hall_linked:
        raise HTTPException(status_code=400, detail="Hall is not linked to this exam session")

    # Verify user
    user = db.query(User).filter(User.id == assignment.invigilator_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invigilator not found")
        
    if user.role != "invigilator":
        raise HTTPException(status_code=400, detail="User must be an invigilator")
        
    # Verify no duplicate primary assignment for this hall
    if assignment.role == "primary":
        existing_primary = db.query(Assignment).filter(
            Assignment.exam_session_id == session_id,
            Assignment.hall_id == assignment.hall_id,
            Assignment.role == "primary"
        ).first()
        if existing_primary:
            raise HTTPException(status_code=400, detail="A primary invigilator is already assigned to this hall")

    new_assignment = Assignment(
        exam_session_id=session_id,
        invigilator_id=assignment.invigilator_id,
        hall_id=assignment.hall_id,
        role=assignment.role
    )
    
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return new_assignment

@router.delete("/{session_id}/assignments/{assignment_id}")
def remove_invigilator(
    session_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
) -> Any:
    """
    Remove an invigilator assignment. Assigned admin only.
    """
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id, 
        Assignment.exam_session_id == session_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    _require_admin_assigned_to_exam(db, session_id, current_user)
        
    db.delete(assignment)
    db.commit()
    return {"message": "Assignment successfully removed"}


@router.get("/{session_id}/report")
def get_session_report(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Aggregate detection events, assignment durations, and hall summaries
    for a given exam session ΓÇö used for the admin Reports tab detail view.
    """
    session = (
        db.query(ExamSession)
        .options(
            selectinload(ExamSession.assignments),
            selectinload(ExamSession.halls),
        )
        .filter(ExamSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    _require_exam_observer(db, session_id, current_user)

    # Aggregate detection events
    events = (
        db.query(DetectionEvent)
        .filter(DetectionEvent.exam_session_id == session_id)
        .order_by(DetectionEvent.timestamp)
        .all()
    )

    alerts = (
        db.query(Alert)
        .filter(Alert.exam_session_id == session_id)
        .all()
    )
    alerts_by_event_id = {
        str(alert.detection_event_id): alert
        for alert in alerts
        if alert.detection_event_id is not None
    }

    total_events = len(events)
    high_severity = sum(1 for e in events if e.severity == "high")
    medium_severity = sum(1 for e in events if e.severity == "medium")
    low_severity = sum(1 for e in events if e.severity == "low")
    confirmed_incidents = sum(1 for a in alerts if a.status == "confirmed")
    cancelled_incidents = sum(1 for a in alerts if a.status in {"cancelled", "false_positive"})

    # Hall summaries
    hall_summaries = []
    for hall in session.halls:
        hall_assignments = [
            a for a in session.assignments if a.hall_id == hall.id
        ]
        # Duration in minutes
        duration_minutes = None
        if hall_assignments:
            a = hall_assignments[0]
            if a.monitoring_started_at and a.monitoring_ended_at:
                started_at = _aware_utc(a.monitoring_started_at)
                ended_at = _aware_utc(a.monitoring_ended_at)
                duration_minutes = int(
                    (ended_at - started_at).total_seconds() / 60
                )
            elif a.monitoring_started_at:
                started_at = _aware_utc(a.monitoring_started_at)
                duration_minutes = int(
                    (datetime.now(timezone.utc) - started_at).total_seconds() / 60
                )
        hall_events = [e for e in events if str(e.device_id) in [
            str(d.id) for d in hall.devices if d.deleted_at is None
        ]] if hasattr(hall, "devices") else []
        hall_summaries.append({
            "hall_id": str(hall.id),
            "hall_name": hall.name,
            "monitoring_started_at": hall_assignments[0].monitoring_started_at.isoformat() if hall_assignments and hall_assignments[0].monitoring_started_at else None,
            "monitoring_ended_at": hall_assignments[0].monitoring_ended_at.isoformat() if hall_assignments and hall_assignments[0].monitoring_ended_at else None,
            "duration_minutes": duration_minutes,
            "events_count": len(hall_events),
        })

    # Timeline: last 20 events
    timeline = []
    for e in events[-20:]:
        alert = alerts_by_event_id.get(str(e.id))
        metadata = e.metadata_json or {}
        timeline.append({
            "id": str(e.id),
            "alert_id": str(alert.id) if alert else None,
            "event_type": e.event_type,
            "severity": e.severity,
            "timestamp": e.timestamp.isoformat(),
            "confidence_score": float(e.confidence_score) if e.confidence_score else None,
            "student_position": e.student_position,
            "alert_status": alert.status if alert else "detected",
            "confirmed_at": alert.confirmed_at.isoformat() if alert and alert.confirmed_at else None,
            "cancelled_at": alert.cancelled_at.isoformat() if alert and alert.cancelled_at else None,
            "resolution_notes": alert.resolution_notes if alert else None,
            "video_clip_path": e.video_clip_path,
            "audio_clip_path": e.audio_clip_path,
            "snapshot_file": metadata.get("snapshot_file"),
            "device_id": str(e.device_id) if e.device_id else None,
        })

    return {
        "session_id": str(session.id),
        "exam_name": session.exam_name,
        "exam_type": session.exam_type,
        "status": session.status,
        "scheduled_start": session.scheduled_start.isoformat() if session.scheduled_start else None,
        "scheduled_end": session.scheduled_end.isoformat() if session.scheduled_end else None,
        "actual_start": session.actual_start.isoformat() if session.actual_start else None,
        "actual_end": session.actual_end.isoformat() if session.actual_end else None,
        "student_count": session.student_count,
        "kpis": {
            "total_events": total_events,
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
            "detected_alerts": len(alerts),
            "confirmed_incidents": confirmed_incidents,
            "cancelled_incidents": cancelled_incidents,
        },
        "halls": hall_summaries,
        "timeline": timeline,
    }
