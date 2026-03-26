import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.db.models.users import User
from src.thaqib.core.security import get_password_hash
from src.thaqib.core.limiter import limiter
from fastapi import Request

router = APIRouter()

# Schema specifically for the one-time setup payload
class SetupSystemPayload(BaseModel):
    institution_name: str = Field(..., min_length=2, max_length=150)
    admin: str = Field(..., min_length=2, max_length=100)
    logo_url: str | None = Field(None, max_length=500)

@router.post("/install", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
def install_system(
    request: Request,
    payload: SetupSystemPayload, 
    db: Session = Depends(get_db)
) -> Any:
    """
    One-time installation endpoint. Creates the root institution and the primary admin user.
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
        
    # 1. Create Institution
    inst = Institution(
        name=payload.institution_name,
        logo_url=payload.logo_url
    )
    db.add(inst)
    db.flush() # flush to get the inst.id
    
    # Generate robust defaults from the 3 variables format
    generated_username = payload.admin.lower().strip().replace(" ", "_")
    generated_email = f"{generated_username}@admin.local"
    # Using a robust default password for the initial admin
    default_password = "Admin_Password123!"
    
    # 2. Create Admin User
    admin_user = User(
        institution_id=inst.id,
        username=generated_username,
        password_hash=get_password_hash(default_password),
        full_name=payload.admin,
        email=generated_email,
        role="admin",
        status="active"
    )
    db.add(admin_user)
    
    db.commit()
    db.refresh(inst)
    db.refresh(admin_user)
    
    return {
        "message": "System installed successfully",
        "institution_id": inst.id,
        "admin_id": admin_user.id,
        "generated_credentials": {
            "username": generated_username,
            "password": default_password
        }
    }
