import uuid
from datetime import datetime
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict, Field


# ---- ingest (scanner → server) -------------------------------------------
class RfSighting(BaseModel):
    """One device the node heard. The raw MAC is hashed server-side and discarded."""
    mac: str = Field(..., description="Raw MAC; hashed on receipt, never stored in clear")
    name: Optional[str] = None
    rssi: Optional[int] = None
    signal_type: str = "ble"  # 'ble' | 'wifi'
    seen_at: Optional[datetime] = None


class RfPushPayload(BaseModel):
    detections: List[RfSighting]
    batch_ts: Optional[datetime] = None


class RfPushResult(BaseModel):
    recorded: int
    alerts_raised: int
    baseline_active: bool
    whitelisted_added: int


# ---- scanner registration -------------------------------------------------
class RfScannerCreate(BaseModel):
    hall_id: uuid.UUID
    identifier: str
    position: Optional[Dict] = None
    ip_address: Optional[str] = None


class RfScannerResponse(BaseModel):
    id: uuid.UUID
    hall_id: uuid.UUID
    identifier: str
    position: Optional[Dict] = None
    ip_address: Optional[str] = None
    status: str
    last_seen: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RfScannerRegistered(RfScannerResponse):
    # The plaintext pre-shared key, returned exactly once at registration time.
    api_key: str


# ---- baseline / dashboard -------------------------------------------------
class RfBaselineStartResponse(BaseModel):
    hall_id: uuid.UUID
    baseline_until: datetime
    duration_seconds: int


class RfWhitelistResponse(BaseModel):
    id: uuid.UUID
    hall_id: uuid.UUID
    device_name: Optional[str] = None
    device_role: str
    baseline_rssi: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class RfScannerPlacement(BaseModel):
    """Pin a scanner node to a point on a camera view (normalized 0–1 coords)."""
    camera_id: str
    norm_pos: tuple[float, float]


class RfUnknownDevice(BaseModel):
    """One row in the per-hall dashboard RF badge / feed overlay."""
    device_name: Optional[str] = None
    signal_type: str
    rssi: Optional[int] = None
    estimated_zone: Optional[str] = None
    last_seen: datetime
    is_spike: bool = False
    # Where to draw it: the reporting scanner's pin on a camera, if placed.
    scanner_id: Optional[uuid.UUID] = None
    camera_id: Optional[str] = None
    norm_pos: Optional[List[float]] = None
