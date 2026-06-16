import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    stream_url: Optional[str] = Field(None, max_length=500)
    position: dict = Field(default_factory=dict)
    coverage_area: Optional[dict] = None
    status: Optional[str] = "offline"

class DeviceCreate(DeviceBase):
    hall_id: uuid.UUID

    @model_validator(mode="after")
    def require_camera_stream_url(self) -> "DeviceCreate":
        if self.type == "camera" and not (self.stream_url or "").strip():
            raise ValueError("Camera devices require stream_url")
        return self

class DeviceUpdate(BaseModel):
    identifier: Optional[str] = None
    ip_address: Optional[str] = None
    stream_url: Optional[str] = None
    position: Optional[dict] = None
    coverage_area: Optional[dict] = None
    status: Optional[str] = None

class MicPlacement(BaseModel):
    camera_id: str = Field(..., min_length=1)
    norm_pos: List[float] = Field(..., min_length=2, max_length=2)

    @model_validator(mode="after")
    def require_normalized_position(self) -> "MicPlacement":
        if any(value < 0 or value > 1 for value in self.norm_pos):
            raise ValueError("norm_pos values must be between 0 and 1")
        return self

class DevicePlacementsUpdate(BaseModel):
    placements: List[MicPlacement] = Field(default_factory=list)

class DeviceResponse(DeviceBase):
    id: uuid.UUID
    hall_id: uuid.UUID
    last_health_check: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
