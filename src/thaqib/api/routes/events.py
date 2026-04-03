import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.events import DetectionEvent
from src.thaqib.db.models.exams import ExamSession
from src.thaqib.schemas.events import DetectionEventCreate, DetectionEventResponse
from src.thaqib.api.ws_manager import manager
from src.thaqib.core.limiter import limiter

router = APIRouter()

@router.post("/", response_model=DetectionEventResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def ingest_event(
    request: Request,
    event_in: DetectionEventCreate, 
    db: Session = Depends(get_db)
) -> Any:
    """
    Ingest a new detection event from the AI pipeline and broadcast it via WebSocket.
    Not strictly requiring an admin/user token here as it can be submitted by pipelines
    auth-less internally or with an internal machine token eventually.
    """
    session = db.query(ExamSession).filter(ExamSession.id == event_in.exam_session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Exam session not found")
        
    new_event = DetectionEvent(
        exam_session_id=event_in.exam_session_id,
        device_id=event_in.device_id,
        event_type=event_in.event_type,
        severity=event_in.severity,
        student_position=event_in.student_position,
        timestamp=event_in.timestamp,
        confidence_score=event_in.confidence_score,
        video_clip_path=event_in.video_clip_path,
        audio_clip_path=event_in.audio_clip_path,
        metadata_json=event_in.metadata_json
    )
    
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    
    # Broadcast event via WebSocket
    event_msg = {
        "action": "new_detection_event",
        "data": {
            "id": str(new_event.id),
            "exam_session_id": str(new_event.exam_session_id),
            "device_id": str(new_event.device_id) if new_event.device_id else None,
            "event_type": new_event.event_type,
            "severity": new_event.severity,
            "student_position": new_event.student_position,
            "timestamp": new_event.timestamp.isoformat(),
            "confidence_score": float(new_event.confidence_score) if new_event.confidence_score else None
        }
    }
    await manager.broadcast(event_msg)
    
    return new_event

@router.get("/", response_model=List[DetectionEventResponse])
@limiter.limit("30/minute")
def read_events(
    request: Request,
    exam_session_id: uuid.UUID,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
) -> Any:
    """
    Retrieve detection events for a specific exam session.
    """
    events = db.query(DetectionEvent).filter(DetectionEvent.exam_session_id == exam_session_id).offset(skip).limit(limit).all()
    return events
