import uuid
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

# Hall Schemas
class HallBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    building: Optional[str] = Field(None, max_length=100)
    floor: Optional[str] = Field(None, max_length=50)
    capacity: int = Field(..., gt=0, le=1000)
    layout_map: Optional[dict] = None
    image: Optional[str] = None
    status: Optional[str] = "not_ready"

class HallCreate(HallBase):
    institution_id: uuid.UUID

class HallUpdate(HallBase):
    name: Optional[str] = None
    capacity: Optional[int] = None

class HallResponse(HallBase):
    id: uuid.UUID
    institution_id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

# Institution Schemas
class InstitutionBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=20, pattern="^[a-zA-Z0-9_-]+$")
    contact_email: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = Field(None, max_length=500)

class InstitutionCreate(InstitutionBase):
    pass

class InstitutionUpdate(InstitutionBase):
    name: Optional[str] = None
    code: Optional[str] = None

class InstitutionResponse(InstitutionBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)

# Device Schemas
class DeviceBase(BaseModel):
    type: str = Field(..., pattern="^(camera|microphone|other)$")
    identifier: str = Field(..., min_length=2, max_length=100)
    ip_address: Optional[str] = Field(None, pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    stream_url: str = Field(..., max_length=500)
    position: dict
    coverage_area: Optional[dict] = None
    status: Optional[str] = "offline"

class DeviceCreate(DeviceBase):
    hall_id: uuid.UUID

class DeviceUpdate(BaseModel):
    identifier: Optional[str] = None
    ip_address: Optional[str] = None
    stream_url: Optional[str] = None
    position: Optional[dict] = None
    coverage_area: Optional[dict] = None
    status: Optional[str] = None

class DeviceResponse(DeviceBase):
    id: uuid.UUID
    hall_id: uuid.UUID
    last_health_check: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
