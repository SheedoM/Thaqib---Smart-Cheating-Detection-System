import uuid
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.db.models.users import User
from src.thaqib.schemas.infrastructure import InstitutionCreate, InstitutionResponse, InstitutionUpdate
from src.thaqib.api.dependencies import RequireRole, get_scope, get_current_active_user
from src.thaqib.core.limiter import limiter

router = APIRouter()

# Super admin only restriction
require_super_admin = RequireRole(["super_admin"])
require_admin_or_super_admin = RequireRole(["admin", "super_admin"])


class CollegeCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    contact_email: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)

@router.post("/", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_institution(
    request: Request,
    institution: InstitutionCreate, 
    db: Session = Depends(get_db),
    _ = Depends(require_super_admin)
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
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Retrieve institutions accessible to the caller (self + children).
    """
    institutions = (
        db.query(Institution)
        .filter(Institution.id.in_(scope))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return institutions

@router.get("/{institution_id}", response_model=InstitutionResponse)
def read_institution(
    institution_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Get institution by ID. Returns 404 for out-of-scope institutions.
    """
    inst = db.query(Institution).filter(
        Institution.id == institution_id,
        Institution.id.in_(scope),
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
    return inst


@router.post("/colleges", response_model=InstitutionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_college(
    request: Request,
    college: CollegeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
) -> Any:
    """
    University super admin creates a child college.
    Only available when the caller's institution type is 'university'.
    """
    root = db.query(Institution).filter(Institution.id == current_user.institution_id).first()
    if not root or root.type != "university":
        raise HTTPException(status_code=403, detail="Only university accounts can create colleges")

    if college.code:
        dup = db.query(Institution).filter(Institution.code == college.code).first()
        if dup:
            raise HTTPException(status_code=400, detail="Institution code already exists")

    child = Institution(
        name=college.name,
        code=college.code,
        contact_email=college.contact_email,
        logo_url=college.logo_url,
        address=college.address,
        type="college",
        parent_id=current_user.institution_id,
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child

@router.put("/{institution_id}", response_model=InstitutionResponse)
@limiter.limit("10/minute")
def update_institution(
    request: Request,
    institution_id: uuid.UUID,
    institution_in: InstitutionUpdate,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Update an institution within accessible institutions.
    """
    inst = db.query(Institution).filter(
        Institution.id == institution_id,
        Institution.id.in_(scope),
    ).first()
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
@limiter.limit("5/minute")
def delete_institution(
    request: Request,
    institution_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_super_admin),
) -> Any:
    """
    Delete an institution. Super admin only, within accessible institutions.
    """
    inst = db.query(Institution).filter(
        Institution.id == institution_id,
        Institution.id.in_(scope),
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    db.delete(inst)
    db.commit()
    return inst
