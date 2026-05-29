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
    role: Optional[str] = None
    status: Optional[str] = None
    ptt_id: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=72)

class UserResponse(UserBase):
    id: uuid.UUID
    institution_id: uuid.UUID
    status: str
    ptt_id: Optional[str] = None
    image: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class SessionResponse(BaseModel):
    token_type: str = "cookie"
    csrf_token: str
    user: UserResponse
