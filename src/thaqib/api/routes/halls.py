import uuid
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Hall, Institution
from src.thaqib.schemas.infrastructure import HallCreate, HallResponse, HallUpdate
from src.thaqib.api.dependencies import RequireRole

router = APIRouter()

# Admin only restriction
require_admin = RequireRole(["admin"])

@router.post("/", response_model=HallResponse, status_code=status.HTTP_201_CREATED)
def create_hall(
    hall: HallCreate, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Create a new hall. Admin only.
    """
    inst = db.query(Institution).filter(Institution.id == hall.institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    db_obj = db.query(Hall).filter(
        Hall.name == hall.name, 
        Hall.institution_id == hall.institution_id
    ).first()
    
    if db_obj:
        raise HTTPException(
            status_code=400,
            detail="A hall with this name already exists in the institution.",
        )
        
    new_hall = Hall(
        institution_id=hall.institution_id,
        name=hall.name,
        building=hall.building,
        floor=hall.floor,
        capacity=hall.capacity,
        layout_map=hall.layout_map,
        status=hall.status
    )
    db.add(new_hall)
    db.commit()
    db.refresh(new_hall)
    return new_hall

@router.get("/", response_model=List[HallResponse])
def read_halls(
    institution_id: Optional[uuid.UUID] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Retrieve halls. Can be filtered by institution. Admin only.
    """
    query = db.query(Hall)
    if institution_id:
        query = query.filter(Hall.institution_id == institution_id)
        
    halls = query.offset(skip).limit(limit).all()
    return halls

@router.get("/{hall_id}", response_model=HallResponse)
def read_hall(
    hall_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Get hall by ID. Admin only.
    """
    hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
    return hall

@router.put("/{hall_id}", response_model=HallResponse)
def update_hall(
    hall_id: uuid.UUID, 
    hall_in: HallUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Update a hall. Admin only.
    """
    hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
        
    update_data = hall_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(hall, field, value)
        
    db.add(hall)
    db.commit()
    db.refresh(hall)
    return hall

@router.delete("/{hall_id}", response_model=HallResponse)
def delete_hall(
    hall_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Delete a hall. Admin only.
    """
    hall = db.query(Hall).filter(Hall.id == hall_id).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
        
    db.delete(hall)
    db.commit()
    return hall
