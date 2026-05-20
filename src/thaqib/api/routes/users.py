import uuid
from pathlib import Path
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.users import User
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.schemas.users import UserCreate, UserResponse, UserUpdate
from src.thaqib.api.dependencies import RequireRole
from src.thaqib.core.security import get_password_hash
from src.thaqib.core.limiter import limiter

router = APIRouter()

# Admin only restriction
require_admin = RequireRole(["admin"])

UPLOADS_DIR = Path("uploads/users")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
MAX_IMAGE_SIZE = 2 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("/upload-image")
async def upload_user_image(
    image: UploadFile = File(...),
    _ = Depends(require_admin),
) -> Any:
    """
    Upload an invigilator/referee profile image and return a public URL.
    """
    suffix = ALLOWED_IMAGE_TYPES.get(image.content_type or "")
    if not suffix:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed.")

    content = await image.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image must be 2MB or smaller.")

    filename = f"{uuid.uuid4().hex}{suffix}"
    destination = UPLOADS_DIR / filename
    destination.write_bytes(content)
    return {"url": f"/uploads/users/{filename}"}

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_user(
    request: Request,
    user: UserCreate, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Create a new user. Admin only.
    """
    inst = db.query(Institution).filter(Institution.id == user.institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")
        
    db_obj = db.query(User).filter(User.username == user.username).first()
    if db_obj:
        raise HTTPException(
            status_code=400,
            detail="A user with this username already exists.",
        )
        
    new_user = User(
        institution_id=user.institution_id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        image=getattr(user, "image", None),
        role=user.role,
        password_hash=get_password_hash(user.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
        
    return new_user

@router.get("/", response_model=List[UserResponse])
def read_users(
    institution_id: Optional[uuid.UUID] = None,
    role: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Retrieve users. Can be filtered by institution and role. Admin only.
    """
    query = db.query(User)
    if institution_id:
        query = query.filter(User.institution_id == institution_id)
    if role:
        query = query.filter(User.role == role)
        
    users = query.offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Get user by ID. Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{user_id}", response_model=UserResponse)
@limiter.limit("20/minute")
def update_user(
    request: Request,
    user_id: uuid.UUID, 
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Update a user. Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    update_data = user_in.model_dump(exclude_unset=True)
    if "username" in update_data:
        existing = db.query(User).filter(User.username == update_data["username"], User.id != user_id).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="A user with this username already exists.",
            )

    password = update_data.pop("password", None)
    for field, value in update_data.items():
        setattr(user, field, value)
    if password:
        user.password_hash = get_password_hash(password)
        
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}", response_model=UserResponse)
@limiter.limit("10/minute")
def delete_user(
    request: Request,
    user_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Delete a user. Admin only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    db.delete(user)
    db.commit()
    return user
