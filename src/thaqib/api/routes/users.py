import uuid
from pathlib import Path
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.users import User
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.schemas.users import UserCreate, UserResponse, UserUpdate
from src.thaqib.api.dependencies import RequireRole, get_current_user, get_scope
from src.thaqib.core.security import get_password_hash, verify_password
from src.thaqib.core.limiter import limiter

router = APIRouter()

require_admin_or_super_admin = RequireRole(["admin", "super_admin"])

class PasswordChangePayload(BaseModel):
    current_password: str
    new_password: str

@router.put("/me/password", status_code=200)
@limiter.limit("5/minute")
def change_my_password(
    request: Request,
    payload: PasswordChangePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Allow any authenticated user to change their own password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل")
    current_user.password_hash = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"message": "تم تغيير كلمة المرور بنجاح"}

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
    _ = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Upload an admin/invigilator profile image and return a public URL.
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
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Create a new user within accessible institutions.
    College admins may create invigilators; only super admins may create admins.
    """
    if user.institution_id not in scope:
        raise HTTPException(status_code=404, detail="Institution not found")
    if current_user.role == "admin" and user.role != "invigilator":
        raise HTTPException(status_code=403, detail="Only super admins can create admin users")
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
        role=user.role,
        password_hash=get_password_hash(user.password),
        image=user.image
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
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Retrieve users scoped to the caller's accessible institutions.
    Exam admins see only invigilators.
    """
    query = db.query(User).filter(User.institution_id.in_(scope))
    if institution_id:
        if institution_id not in scope:
            return []
        query = query.filter(User.institution_id == institution_id)
    if current_user.role == "admin":
        query = query.filter(User.role == "invigilator")
    if role:
        query = query.filter(User.role == role)

    users = query.offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Get user by ID. Returns 404 for out-of-scope users.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.institution_id.in_(scope),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role == "admin" and user.role != "invigilator":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user

@router.put("/{user_id}", response_model=UserResponse)
@limiter.limit("20/minute")
def update_user(
    request: Request,
    user_id: uuid.UUID, 
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Update a user within accessible institutions.
    College admins may manage invigilators only; admin accounts are super-admin governed.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.institution_id.in_(scope),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    update_data = user_in.model_dump(exclude_unset=True)
    if current_user.role == "admin":
        requested_role = update_data.get("role")
        if user.role != "invigilator" or (requested_role is not None and requested_role != "invigilator"):
            raise HTTPException(status_code=403, detail="Only super admins can manage admin users")

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
    scope = Depends(get_scope),
    current_user: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Delete a user within accessible institutions.
    College admins may delete invigilators only.
    """
    user = db.query(User).filter(
        User.id == user_id,
        User.institution_id.in_(scope),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.role == "admin" and user.role != "invigilator":
        raise HTTPException(status_code=403, detail="Only super admins can manage admin users")
        
    db.delete(user)
    db.commit()
    return user
