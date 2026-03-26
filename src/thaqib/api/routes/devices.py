import uuid
from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.infrastructure import Device, Hall
from src.thaqib.schemas.infrastructure import DeviceCreate, DeviceResponse, DeviceUpdate
from src.thaqib.api.dependencies import RequireRole

router = APIRouter()

# Admin only restriction
require_admin = RequireRole(["admin"])

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    device: DeviceCreate, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Create a new device. Admin only.
    """
    hall = db.query(Hall).filter(Hall.id == device.hall_id).first()
    if not hall:
        raise HTTPException(status_code=404, detail="Hall not found")
        
    db_obj = db.query(Device).filter(
        Device.identifier == device.identifier, 
        Device.hall_id == device.hall_id
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
        stream_url=device.stream_url,
        position=device.position,
        coverage_area=device.coverage_area,
        status=device.status
    )
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    
    # Optional handling of datetime for response compatibility
    if new_device.last_health_check:
        new_device.last_health_check = new_device.last_health_check.isoformat()
        
    return new_device

@router.get("/", response_model=List[DeviceResponse])
def read_devices(
    hall_id: Optional[uuid.UUID] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Retrieve devices. Can be filtered by hall. Admin only.
    """
    query = db.query(Device)
    if hall_id:
        query = query.filter(Device.hall_id == hall_id)
        
    devices = query.offset(skip).limit(limit).all()
    # Handle datetime serialization if necessary (pydantic handles it usually when model allows string or datetime)
    for device in devices:
        if device.last_health_check:
             device.last_health_check = device.last_health_check.isoformat()
    return devices

@router.get("/{device_id}", response_model=DeviceResponse)
def read_device(
    device_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Get device by ID. Admin only.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    if device.last_health_check:
        device.last_health_check = device.last_health_check.isoformat()
    return device

@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: uuid.UUID, 
    device_in: DeviceUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Update a device. Admin only.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    update_data = device_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)
        
    db.add(device)
    db.commit()
    db.refresh(device)
    
    if device.last_health_check:
        device.last_health_check = device.last_health_check.isoformat()
    return device

@router.delete("/{device_id}", response_model=DeviceResponse)
def delete_device(
    device_id: uuid.UUID, 
    db: Session = Depends(get_db),
    _ = Depends(require_admin)
) -> Any:
    """
    Delete a device. Admin only.
    """
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        
    db.delete(device)
    db.commit()
    
    if device.last_health_check:
         device.last_health_check = device.last_health_check.isoformat()
    return device
