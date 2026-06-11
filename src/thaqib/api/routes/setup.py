import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.db.models.users import User
from src.thaqib.core.security import get_password_hash
from src.thaqib.core.limiter import limiter
from fastapi import Request

router = APIRouter()

VALID_INSTITUTION_TYPES = {"university", "college", "school", "standalone"}

class CollegePayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=20)

# Schema specifically for the one-time setup payload
class SetupSystemPayload(BaseModel):
    institution_name: str = Field(..., min_length=2, max_length=150)
    institution_type: str = Field("standalone", description="university | college | school | standalone")
    admin: str = Field(..., min_length=2, max_length=100)
    admin_password: str = Field(..., min_length=12, max_length=128)
    logo_url: str | None = Field(None, max_length=500)
    colleges: Optional[List[CollegePayload]] = Field(
        None,
        description="Optional initial colleges (only used when institution_type='university')",
    )

@router.get("/status")
def get_setup_status(db: Session = Depends(get_db)) -> Any:
    """
    Check if the system has been initialized.
    """
    inst_count = db.query(Institution).count()
    user_count = db.query(User).count()
    return {"is_installed": inst_count > 0 and user_count > 0}

@router.post("/install", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def install_system(
    request: Request,
    payload: SetupSystemPayload, 
    db: Session = Depends(get_db)
) -> Any:
    """
    One-time installation endpoint. Creates the root institution and the primary super admin user.
    Fails if the system has already been initialized.
    """
    # Check if system is already initialized
    inst_count = db.query(Institution).count()
    user_count = db.query(User).count()
    
    if inst_count > 0 or user_count > 0:
        raise HTTPException(
            status_code=400,
            detail="System already initialized. Cannot run setup again."
        )

    inst_type = payload.institution_type.lower().strip()
    if inst_type not in VALID_INSTITUTION_TYPES:
        raise HTTPException(status_code=400, detail=f"institution_type must be one of: {', '.join(VALID_INSTITUTION_TYPES)}")

    # 1. Create root Institution
    inst = Institution(
        name=payload.institution_name,
        logo_url=payload.logo_url,
        type=inst_type,
        parent_id=None,
    )
    db.add(inst)
    db.flush()  # get inst.id

    # Generate robust defaults from the setup form.
    generated_username = payload.admin.lower().strip().replace(" ", "_")
    generated_email = f"{generated_username}@admin.example.com"

    # 2. Create Super Admin User (belongs to the root institution)
    admin_user = User(
        institution_id=inst.id,
        username=generated_username,
        password_hash=get_password_hash(payload.admin_password),
        full_name=payload.admin,
        email=generated_email,
        role="super_admin",
        status="active"
    )
    db.add(admin_user)

    # 3. If university, create any seed colleges
    college_ids = []
    if inst_type == "university" and payload.colleges:
        for c in payload.colleges:
            child = Institution(
                name=c.name,
                code=c.code,
                type="college",
                parent_id=inst.id,
            )
            db.add(child)
            db.flush()
            college_ids.append(str(child.id))

    db.commit()
    db.refresh(inst)
    db.refresh(admin_user)

    return {
        "message": "System installed successfully",
        "institution_id": inst.id,
        "institution_type": inst_type,
        "admin_id": admin_user.id,
        "colleges_created": college_ids,
        "generated_credentials": {
            "username": generated_username,
        }
    }
