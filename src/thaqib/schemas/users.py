import uuid
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# User Schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    role: str

class UserCreate(UserBase):
    password: str
    institution_id: uuid.UUID

class UserResponse(UserBase):
    id: uuid.UUID
    status: str
    ptt_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
