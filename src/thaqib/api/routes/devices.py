import uuid
from datetime import datetime, timezone
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.db.models.users import User
from src.thaqib.schemas.infrastructure import DeviceCreate, DeviceResponse, DeviceUpdate
from src.thaqib.api.dependencies import RequireRole, get_scope
from src.thaqib.core.limiter import limiter

router = APIRouter()

require_admin_or_super_admin = RequireRole(["admin", "super_admin"])


def _get_scoped_hall(db: Session, hall_id: uuid.UUID, scope: set[uuid.UUID]) -> Hall | None:
    return db.query(Hall).filter(
        Hall.id == hall_id,
        Hall.deleted_at.is_(None),
        Hall.institution_id.in_(scope),
    ).first()


def _get_scoped_device(db: Session, device_id: uuid.UUID, scope: set[uuid.UUID]) -> Device | None:
    return (
        db.query(Device)
        .join(Hall, Device.hall_id == Hall.id)
        .filter(
            Device.id == device_id,
            Device.deleted_at.is_(None),
            Hall.deleted_at.is_(None),
            Hall.institution_id.in_(scope),
        )
        .first()
    )

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_device(
    request: Request,
    device: DeviceCreate, 
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Create a new device within accessible halls.
    """
    hall = _get_scoped_hall(db, device.hall_id, scope)
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
        
    db_obj = db.query(Device).filter(
        Device.identifier == device.identifier, 
        Device.hall_id == device.hall_id,
        Device.deleted_at.is_(None)
    ).first()
    
    if db_obj:
        raise HTTPException(
            status_code=400,
            detail="A device with this identifier already exists in the hall.",
        )
        
    new_device = Device(
        hall_id=device.hall_id,
        type=device.type,
        identifier=device.identifier,
        ip_address=device.ip_address,
        stream_url=device.stream_url or "",
        position=device.position,
        coverage_area=device.coverage_area,
        status=device.status or "offline",
        last_health_check=datetime.now(timezone.utc),
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    
    return new_device

@router.get("/", response_model=List[DeviceResponse])
def read_devices(
    hall_id: Optional[uuid.UUID] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Retrieve devices in accessible halls. Can be filtered by hall.
    """
    query = (
        db.query(Device)
        .join(Hall, Device.hall_id == Hall.id)
        .filter(
            Device.deleted_at.is_(None),
            Hall.deleted_at.is_(None),
            Hall.institution_id.in_(scope),
        )
    )
    if hall_id:
        if not _get_scoped_hall(db, hall_id, scope):
            return []
        query = query.filter(Device.hall_id == hall_id)
        
    devices = query.offset(skip).limit(limit).all()
    return devices

@router.get("/{device_id}", response_model=DeviceResponse)
def read_device(
    device_id: uuid.UUID, 
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Get device by ID within accessible halls.
    """
    device = _get_scoped_device(db, device_id, scope)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    return device

@router.put("/{device_id}", response_model=DeviceResponse)
@limiter.limit("20/minute")
def update_device(
    request: Request,
    device_id: uuid.UUID, 
    device_in: DeviceUpdate,
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Update a device within accessible halls.
    """
    device = _get_scoped_device(db, device_id, scope)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    update_data = device_in.model_dump(exclude_unset=True)
    next_stream_url = update_data.get("stream_url", device.stream_url)
    if device.type == "camera" and not (next_stream_url or "").strip():
        raise HTTPException(status_code=422, detail="Camera devices require stream_url")

    for field, value in update_data.items():
        setattr(device, field, value if field != "stream_url" or value is not None else "")
    device.last_health_check = datetime.now(timezone.utc)
        
    db.add(device)
    db.commit()
    db.refresh(device)
    
    return device

@router.delete("/{device_id}", response_model=DeviceResponse)
@limiter.limit("10/minute")
def delete_device(
    request: Request,
    device_id: uuid.UUID, 
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_admin_or_super_admin),
) -> Any:
    """
    Delete a device within accessible halls.
    """
    device = _get_scoped_device(db, device_id, scope)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.deleted_at = datetime.now(timezone.utc)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device
