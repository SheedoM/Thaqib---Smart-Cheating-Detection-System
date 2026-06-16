import uuid
from datetime import datetime, timezone
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Hall, Institution
from src.thaqib.schemas.infrastructure import HallCreate, HallResponse, HallUpdate
from src.thaqib.api.dependencies import RequireRole, get_scope, get_current_active_user
from src.thaqib.db.models.users import User
from src.thaqib.core.limiter import limiter

router = APIRouter()

require_admin_or_super_admin = RequireRole(["admin", "super_admin"])

@router.post("/", response_model=HallResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_hall(
    request: Request,
    hall: HallCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_super_admin),
    scope = Depends(get_scope),
) -> Any:
    """
    Create a new hall within accessible institutions.
    """
    if hall.institution_id not in scope:
        raise HTTPException(status_code=404, detail="Institution not found")
    inst = db.query(Institution).filter(Institution.id == hall.institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    db_obj = db.query(Hall).filter(
        Hall.name == hall.name,
        Hall.institution_id == hall.institution_id,
        Hall.deleted_at.is_(None)
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
        image=hall.image,
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
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Retrieve halls scoped to the caller's accessible institutions.
    """
    query = db.query(Hall).filter(
        Hall.deleted_at.is_(None),
        Hall.institution_id.in_(scope),
    )
    if institution_id:
        if institution_id not in scope:
            return []
        query = query.filter(Hall.institution_id == institution_id)

    halls = query.offset(skip).limit(limit).all()
    return halls

@router.get("/{hall_id}", response_model=HallResponse)
def read_hall(
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Get hall by ID. Returns 404 for out-of-scope halls.
    """
    hall = db.query(Hall).filter(
        Hall.id == hall_id,
        Hall.deleted_at.is_(None),
        Hall.institution_id.in_(scope),
    ).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
    return hall

@router.put("/{hall_id}", response_model=HallResponse)
@limiter.limit("10/minute")
def update_hall(
    request: Request,
    hall_id: uuid.UUID,
    hall_in: HallUpdate,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Update a hall within accessible institutions.
    """
    hall = db.query(Hall).filter(
        Hall.id == hall_id,
        Hall.deleted_at.is_(None),
        Hall.institution_id.in_(scope),
    ).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")

    update_data = hall_in.model_dump(exclude_unset=True)

    # Guard duplicate name within same institution
    if "name" in update_data:
        dup = db.query(Hall).filter(
            Hall.name == update_data["name"],
            Hall.institution_id == hall.institution_id,
            Hall.id != hall_id,
            Hall.deleted_at.is_(None)
        ).first()
        if dup:
            raise HTTPException(
                status_code=400,
                detail="A hall with this name already exists in the institution.",
            )

    for field, value in update_data.items():
        setattr(hall, field, value)

    db.add(hall)
    db.commit()
    db.refresh(hall)
    return hall

@router.delete("/{hall_id}", response_model=HallResponse)
@limiter.limit("5/minute")
def delete_hall(
    request: Request,
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Delete a hall within accessible institutions.
    """
    hall = db.query(Hall).filter(
        Hall.id == hall_id,
        Hall.deleted_at.is_(None),
        Hall.institution_id.in_(scope),
    ).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")

    # Soft delete the hall and cascade to its devices
    now = datetime.now(timezone.utc)
    hall.deleted_at = now
    for device in hall.devices:
        device.deleted_at = now

    db.add(hall)
    db.commit()
    db.refresh(hall)
    return hall
