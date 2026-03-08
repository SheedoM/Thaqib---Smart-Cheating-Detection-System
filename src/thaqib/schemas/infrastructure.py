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
    pass

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
