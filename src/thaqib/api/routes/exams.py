import uuid
from datetime import datetime, timezone
from typing import List, Any, Optional
import cv2
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, selectinload

from src.thaqib.db.database import get_db
from src.thaqib.db.models.exams import ExamSession, Assignment
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User
from src.thaqib.schemas.exams import (
    ExamSessionCreate, ExamSessionResponse, ExamSessionUpdate, 
    AssignmentCreate, AssignmentResponse, AssignmentDetailedResponse
)
from src.thaqib.api.dependencies import RequireRole, get_current_user
from src.thaqib.core.limiter import limiter
from src.thaqib.api.routes import stream

router = APIRouter()
require_admin = RequireRole(["admin"])
require_invigilator = RequireRole(["invigilator", "referee", "admin"])


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
    if not hall or all(h.id != hall_id for h in session.halls):
        raise HTTPException(status_code=404, detail="Hall is not linked to this exam session")

    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id,
    ).first()

    if current_user.role not in {"admin", "referee"}:
        if not assignment or assignment.invigilator_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not assigned to monitor this hall")

    return session, hall, assignment

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
    current_user: User = Depends(require_invigilator)
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
    if current_user.role != "admin" and assignment.invigilator_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not assigned to monitor this hall")
        
    stream.start_hall_monitoring(hall_id, session_id, db)
    return {"status": "monitoring started"}


@router.get("/{session_id}/halls/{hall_id}/readiness")
def get_hall_readiness(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_invigilator)
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

@router.post("/{session_id}/halls/{hall_id}/monitoring/stop")
def stop_monitoring(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_invigilator)
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
    if current_user.role != "admin" and assignment.invigilator_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not assigned to this hall")
        
    stream.stop_hall_monitoring(hall_id, session_id, db)
    return {"status": "monitoring stopped"}

@router.get("/{session_id}/halls/{hall_id}/status")
def get_hall_monitoring_status(
    session_id: uuid.UUID,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    _ = Depends(require_invigilator)
) -> Any:
    """
    Get the current monitoring status of a specific hall in a session.
    """
    assignment = db.query(Assignment).filter(
        Assignment.exam_session_id == session_id,
        Assignment.hall_id == hall_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    is_active = assignment.monitoring_started_at is not None and assignment.monitoring_ended_at is None
    
    return {
        "hall_id": str(hall_id),
        "hall_name": assignment.hall.name,
        "exam_name": assignment.exam_session.exam_name,
        "is_active": is_active,
        "started_at": assignment.monitoring_started_at,
        "ended_at": assignment.monitoring_ended_at,
        "stats": {
            "student_count": assignment.exam_session.student_count or 0,
            "active_alerts": 0,
        },
        "alerts": [],
    }

@router.post("/", response_model=ExamSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_exam_session(
    request: Request,
    session_data: ExamSessionCreate, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Create a new exam session. Admin only.
    """
    # Verify halls exist
    halls = []
    if session_data.hall_ids:
        halls = db.query(Hall).filter(Hall.id.in_(session_data.hall_ids), Hall.deleted_at.is_(None)).all()
        if len(halls) != len(session_data.hall_ids):
            raise HTTPException(status_code=400, detail="One or more halls could not be found.")

    new_session = ExamSession(
        exam_name=session_data.exam_name,
        exam_type=session_data.exam_type,
        scheduled_start=session_data.scheduled_start,
        scheduled_end=session_data.scheduled_end,
        status=session_data.status,
        student_count=session_data.student_count,
        configuration=session_data.configuration
    )
    
    # Associate halls
    new_session.halls = halls
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

@router.get("/", response_model=List[ExamSessionResponse])
def read_exam_sessions(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Retrieve exam sessions. Admin only.
    """
    sessions = db.query(ExamSession).offset(skip).limit(limit).all()
    return sessions

@router.get("/{session_id}", response_model=ExamSessionResponse)
def read_exam_session(
    session_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Get exam session by ID. Admin only.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
    return session

@router.put("/{session_id}", response_model=ExamSessionResponse)
@limiter.limit("10/minute")
def update_exam_session(
    request: Request,
    session_id: uuid.UUID, 
    session_in: ExamSessionUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Update an exam session. Admin only.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
        
    update_data = session_in.model_dump(exclude_unset=True)
    hall_ids = update_data.pop("hall_ids", None)
    if hall_ids is not None:
        halls = db.query(Hall).filter(Hall.id.in_(hall_ids), Hall.deleted_at.is_(None)).all()
        if len(halls) != len(hall_ids):
            raise HTTPException(status_code=400, detail="One or more halls could not be found.")
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
    _ = Depends(require_admin)
) -> Any:
    """
    Delete an exam session. Admin only.
    """
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
        
    db.delete(session)
    db.commit()
    return session

@router.post("/{session_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def assign_invigilator(
    request: Request,
    session_id: uuid.UUID,
    assignment: AssignmentCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Assign an invigilator to an exam session. Admin/Referee only.
    """
    # Verify session
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
        
    # Verify hall is linked to this session
    hall_linked = any(h.id == assignment.hall_id for h in session.halls)
    if not hall_linked:
        raise HTTPException(status_code=400, detail="Hall is not linked to this exam session")

    # Verify user
    user = db.query(User).filter(User.id == assignment.invigilator_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invigilator not found")
        
    if user.role not in ["invigilator", "referee"]:
        raise HTTPException(status_code=400, detail="User must be an invigilator or referee")
        
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
    _ = Depends(require_admin)
) -> Any:
    """
    Remove an invigilator assignment. Admin/Referee only.
    """
    assignment = db.query(Assignment).filter(
        Assignment.id == assignment_id, 
        Assignment.exam_session_id == session_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
        
    db.delete(assignment)
    db.commit()
    return {"message": "Assignment successfully removed"}
