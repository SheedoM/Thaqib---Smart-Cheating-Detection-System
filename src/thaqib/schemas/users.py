import uuid
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field

# Token Schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern="^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    role: str = Field(..., pattern="^(super_admin|admin|invigilator)$")
    image: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)
    institution_id: uuid.UUID
    image: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50, pattern="^[a-zA-Z0-9_.-]+$")
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    image: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(super_admin|admin|invigilator)$")
    status: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class UserResponse(UserBase):
    id: uuid.UUID
    institution_id: uuid.UUID
    status: str
    image: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class UserPreferences(BaseModel):
    alert_cue_mode: Literal["sound_vibrate", "sound_only", "vibrate_only", "silent"] = "sound_vibrate"
    alert_volume: int = Field(80, ge=0, le=100)
    browser_notifications_enabled: bool = False
    compact_display: bool = False
    large_text: bool = False

class SessionResponse(BaseModel):
    token_type: str = "cookie"
    csrf_token: str
    user: UserResponse
