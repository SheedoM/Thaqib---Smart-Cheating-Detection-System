import uuid
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict

# Assignment Schemas (Invigilators)
class AssignmentBase(BaseModel):
    invigilator_id: uuid.UUID
    role: Optional[str] = "primary" # 'primary' or 'secondary'

class AssignmentCreate(AssignmentBase):
    pass

class AssignmentResponse(AssignmentBase):
    id: uuid.UUID
    exam_session_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

# ExamSession Schemas
class ExamSessionBase(BaseModel):
    exam_name: str
    exam_type: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    status: Optional[str] = "scheduled" # 'scheduled', 'active', 'completed', 'cancelled'
    student_count: Optional[int] = None
    configuration: Optional[Dict] = None

class ExamSessionCreate(ExamSessionBase):
    hall_ids: List[uuid.UUID] = []

class ExamSessionUpdate(BaseModel):
    exam_name: Optional[str] = None
    exam_type: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    status: Optional[str] = None
    student_count: Optional[int] = None
    configuration: Optional[Dict] = None

class ExamSessionResponse(ExamSessionBase):
    id: uuid.UUID
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None

    # This could include basic info about halls and assignments, 
    # but initially returning just the basic fields to avoid circular dependencies
    model_config = ConfigDict(from_attributes=True)
