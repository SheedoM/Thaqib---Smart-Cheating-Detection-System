import uuid
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.exams import ExamSession, Assignment
from src.thaqib.db.models.infrastructure import Hall
from src.thaqib.db.models.users import User
from src.thaqib.schemas.exams import ExamSessionCreate, ExamSessionResponse, ExamSessionUpdate, AssignmentCreate, AssignmentResponse
from src.thaqib.api.dependencies import RequireRole

router = APIRouter()
require_admin = RequireRole(["admin"])

@router.post("/", response_model=ExamSessionResponse, status_code=status.HTTP_201_CREATED)
def create_exam_session(
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
        halls = db.query(Hall).filter(Hall.id.in_(session_data.hall_ids)).all()
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
def update_exam_session(
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
    for field, value in update_data.items():
        setattr(session, field, value)
        
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.delete("/{session_id}", response_model=ExamSessionResponse)
def delete_exam_session(
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
def assign_invigilator(
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
        
    # Verify user
    user = db.query(User).filter(User.id == assignment.invigilator_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Invigilator not found")
        
    if user.role not in ["invigilator", "referee"]:
        raise HTTPException(status_code=400, detail="User must be an invigilator or referee")
        
    new_assignment = Assignment(
        exam_session_id=session_id,
        invigilator_id=assignment.invigilator_id,
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
