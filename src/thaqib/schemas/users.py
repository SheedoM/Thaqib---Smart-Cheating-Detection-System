import uuid
from typing import Optional
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
    role: str = Field(..., pattern="^(admin|invigilator|referee)$")

class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=72)
    institution_id: uuid.UUID

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None
    ptt_id: Optional[str] = None

class UserResponse(UserBase):
    id: uuid.UUID
    status: str
    ptt_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
