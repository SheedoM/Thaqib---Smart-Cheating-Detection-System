import uuid
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel, ConfigDict

class DetectionEventBase(BaseModel):
    event_type: str
    severity: str # 'low', 'medium', 'high'
    student_position: Dict
    timestamp: datetime
    confidence_score: Optional[float] = None
    video_clip_path: Optional[str] = None
    audio_clip_path: Optional[str] = None
    metadata_json: Optional[Dict] = None

class DetectionEventCreate(DetectionEventBase):
    exam_session_id: uuid.UUID
    device_id: Optional[uuid.UUID] = None

class DetectionEventResponse(DetectionEventBase):
    id: uuid.UUID
    exam_session_id: uuid.UUID
    device_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
