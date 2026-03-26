import uuid
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# Hall Schemas
class HallBase(BaseModel):
    name: str
    building: Optional[str] = None
    floor: Optional[str] = None
    capacity: int
    layout_map: Optional[dict] = None
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
    name: str
    code: Optional[str] = None
    contact_email: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = None

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
    type: str
    identifier: str
    ip_address: Optional[str] = None
    stream_url: str
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
