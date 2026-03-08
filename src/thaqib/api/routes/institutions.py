import uuid
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.schemas.infrastructure import InstitutionCreate, InstitutionResponse, InstitutionUpdate
from src.thaqib.api.dependencies import RequireRole

router = APIRouter()

# Admin only restriction
require_admin = RequireRole(["admin"])

@router.post("/", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
def create_institution(
    institution: InstitutionCreate, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Create new institution. Admin only.
    """
    db_obj = db.query(Institution).filter(Institution.code == institution.code).first()
    if db_obj:
        raise HTTPException(
            status_code=400,
            detail="The institution with this code already exists in the system.",
        )
    inst = Institution(
        name=institution.name,
        code=institution.code,
        contact_email=institution.contact_email,
        logo_url=institution.logo_url,
        address=institution.address
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst

@router.get("/", response_model=List[InstitutionResponse])
def read_institutions(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Retrieve institutions. Admin only.
    """
    institutions = db.query(Institution).offset(skip).limit(limit).all()
    return institutions

@router.get("/{institution_id}", response_model=InstitutionResponse)
def read_institution(
    institution_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Get institution by ID. Admin only.
    """
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    return inst

@router.put("/{institution_id}", response_model=InstitutionResponse)
def update_institution(
    institution_id: uuid.UUID, 
    institution_in: InstitutionUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Update an institution. Admin only.
    """
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    update_data = institution_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inst, field, value)
        
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst

@router.delete("/{institution_id}", response_model=InstitutionResponse)
def delete_institution(
    institution_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Delete an institution. Admin only.
    """
    inst = db.query(Institution).filter(Institution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    db.delete(inst)
    db.commit()
    return inst
