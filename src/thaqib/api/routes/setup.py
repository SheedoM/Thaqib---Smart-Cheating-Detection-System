import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.db.models.users import User
from src.thaqib.core.security import get_password_hash

router = APIRouter()

# Schema specifically for the one-time setup payload
class SetupSystemPayload(BaseModel):
    # Institution Info
    institution_name: str
    logo_url: str = None
    
    # Admin Info
    admin_full_name: str
    admin_username: str
    admin_email: EmailStr
    admin_password: str

@router.post("/install", status_code=status.HTTP_201_CREATED)
def install_system(
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
    
    # 2. Create Admin User
    admin = User(
        institution_id=inst.id,
        username=payload.admin_username,
        password_hash=get_password_hash(payload.admin_password),
        full_name=payload.admin_full_name,
        email=payload.admin_email,
        role="admin",
        status="active"
    )
    db.add(admin)
    
    db.commit()
    db.refresh(inst)
    db.refresh(admin)
    
    return {
        "message": "System installed successfully",
        "institution_id": inst.id,
        "admin_id": admin.id
    }
