"""
RF device-detection API.

  POST /api/v1/rf-push/{scanner_id}/detections   ← scanner nodes (pre-shared key)
  POST /api/v1/rf/scanners                        ← register a node (admin)
  GET  /api/v1/rf/scanners?hall_id=...            ← list nodes (admin)
  POST /api/v1/rf/halls/{hall_id}/baseline        ← start the pre-exam baseline
  GET  /api/v1/rf/halls/{hall_id}/whitelist       ← list whitelisted devices
  GET  /api/v1/rf/halls/{hall_id}/unknown         ← dashboard RF badge feed
"""

import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Any, List

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.thaqib.api.dependencies import RequireRole
from src.thaqib.api.routes import stream, voice
from src.thaqib.core.limiter import limiter
from src.thaqib.db.database import get_db
from src.thaqib.db.models.rf import RfDetection, RfScanner, RfWhitelistEntry
from src.thaqib.db.models.users import User
from src.thaqib.schemas.rf import (
    RfBaselineStartResponse, RfPushPayload, RfPushResult, RfScannerCreate,
    RfScannerPlacement, RfScannerRegistered, RfScannerResponse, RfUnknownDevice,
    RfWhitelistResponse,
)
from src.thaqib.services import rf_detection as rf

router = APIRouter()
require_rf_admin = RequireRole(["admin", "super_admin"])
# Invigilators consume RF data (badge + on-feed markers) but never configure it.
require_rf_viewer = RequireRole(["admin", "super_admin", "invigilator"])


# --------------------------------------------------------------------------
# Scanner-node ingest — authenticated by a per-node pre-shared key, NOT a JWT.
# --------------------------------------------------------------------------
@router.post("/rf-push/{scanner_id}/detections", response_model=RfPushResult)
@limiter.limit("120/minute")
async def push_detections(
    request: Request,
    scanner_id: uuid.UUID,
    payload: RfPushPayload,
    x_rf_key: str | None = Header(default=None, alias="X-RF-Key"),
    db: Session = Depends(get_db),
) -> Any:
    scanner = db.query(RfScanner).filter(RfScanner.id == scanner_id).first()
    if scanner is None or scanner.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    if not x_rf_key or not hmac.compare_digest(rf.hash_key(x_rf_key), scanner.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid scanner key")

    result = rf.process_detections(db, scanner, payload.detections)

    # Surface any raised alerts live: dashboard feed + hall voice channel.
    for ap in result.get("alert_payloads", []):
        stream.push_external_alert({
            "id": ap["id"],
            "exam_session_id": ap["exam_session_id"],
            "hall_id": ap["hall_id"],
            "camera_id": None,
            "camera_name": None,
            "hall_name": None,
            "event_type": "rf_transmission",
            "severity": ap["severity"],
            "timestamp": ap["timestamp"],
            "location": ap["location"],
            "device_name": ap.get("device_name"),
            "estimated_zone": ap.get("estimated_zone"),
            "signal_type": ap.get("signal_type"),
            "rssi": ap.get("rssi"),
            "is_spike": ap.get("is_spike", False),
            "kind": "rf",
        })
        await voice.notify_hall(ap["hall_id"], {
            "type": "rf_alert",
            "alert_id": ap["id"],
            "device_name": ap.get("device_name"),
            "estimated_zone": ap.get("estimated_zone"),
            "reason": ap.get("reason"),
            "is_spike": ap.get("is_spike", False),
            "timestamp": ap["timestamp"],
        })

    return RfPushResult(
        recorded=result["recorded"],
        alerts_raised=result["alerts_raised"],
        baseline_active=result["baseline_active"],
        whitelisted_added=result["whitelisted_added"],
    )


# --------------------------------------------------------------------------
# Scanner registration (admin)
# --------------------------------------------------------------------------
@router.post("/rf/scanners", response_model=RfScannerRegistered, status_code=201)
def register_scanner(
    body: RfScannerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_rf_admin),
) -> Any:
    api_key = secrets.token_urlsafe(32)
    scanner = RfScanner(
        hall_id=body.hall_id,
        identifier=body.identifier,
        position=body.position,
        ip_address=body.ip_address,
        api_key_hash=rf.hash_key(api_key),
        status="offline",
    )
    db.add(scanner)
    db.commit()
    db.refresh(scanner)
    data = RfScannerResponse.model_validate(scanner).model_dump()
    # The plaintext key is returned exactly once; only its hash is stored.
    return RfScannerRegistered(**data, api_key=api_key)


@router.get("/rf/scanners", response_model=List[RfScannerResponse])
def list_scanners(
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_rf_viewer),
) -> Any:
    return (
        db.query(RfScanner)
        .filter(RfScanner.hall_id == hall_id, RfScanner.deleted_at.is_(None))
        .all()
    )


@router.put("/rf/scanners/{scanner_id}/placement", response_model=RfScannerResponse)
def place_scanner(
    scanner_id: uuid.UUID,
    body: RfScannerPlacement,
    db: Session = Depends(get_db),
    _: User = Depends(require_rf_viewer),
) -> Any:
    """Pin a scanner to a point on a camera view, so its detections can be drawn
    on the live feed (mirrors the mic-pin placement model)."""
    scanner = db.query(RfScanner).filter(RfScanner.id == scanner_id).first()
    if scanner is None or scanner.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Scanner not found")
    existing = scanner.position if isinstance(scanner.position, dict) else {}
    scanner.position = {
        **existing,
        "camera_id": body.camera_id,
        "norm_pos": [round(body.norm_pos[0], 4), round(body.norm_pos[1], 4)],
    }
    db.commit()
    db.refresh(scanner)
    return scanner


# --------------------------------------------------------------------------
# Baseline / whitelist (admin)
# --------------------------------------------------------------------------
@router.post("/rf/halls/{hall_id}/baseline", response_model=RfBaselineStartResponse)
def start_baseline(
    hall_id: uuid.UUID,
    seconds: int = rf.BASELINE_SECONDS,
    db: Session = Depends(get_db),
    _: User = Depends(require_rf_admin),
) -> Any:
    seconds = max(30, min(seconds, 1800))
    until = rf.start_baseline(hall_id, seconds)
    return RfBaselineStartResponse(hall_id=hall_id, baseline_until=until, duration_seconds=seconds)


@router.get("/rf/halls/{hall_id}/whitelist", response_model=List[RfWhitelistResponse])
def list_whitelist(
    hall_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_rf_admin),
) -> Any:
    return (
        db.query(RfWhitelistEntry)
        .filter(RfWhitelistEntry.hall_id == hall_id)
        .order_by(RfWhitelistEntry.created_at.desc())
        .all()
    )


# --------------------------------------------------------------------------
# Dashboard RF badge: recent unknown / spiking devices in a hall
# --------------------------------------------------------------------------
@router.get("/rf/halls/{hall_id}/unknown", response_model=List[RfUnknownDevice])
def unknown_devices(
    hall_id: uuid.UUID,
    window_minutes: int = 5,
    db: Session = Depends(get_db),
    _: User = Depends(require_rf_viewer),
) -> Any:
    since = rf._now() - timedelta(minutes=max(1, min(window_minutes, 60)))
    rows = (
        db.query(RfDetection)
        .join(RfScanner, RfDetection.scanner_id == RfScanner.id)
        .filter(RfScanner.hall_id == hall_id, RfDetection.detected_at >= since)
        .order_by(RfDetection.detected_at.desc())
        .all()
    )
    seen: dict[str, RfUnknownDevice] = {}
    for d in rows:
        spike = bool(d.metadata_json and d.metadata_json.get("spike"))
        if d.is_whitelisted and not spike:
            continue  # known and quiet — not a concern
        if d.mac_hash in seen:
            continue  # keep only the most recent sighting per device
        pos = d.scanner.position if (d.scanner and isinstance(d.scanner.position, dict)) else {}
        seen[d.mac_hash] = RfUnknownDevice(
            device_name=d.device_name,
            signal_type=d.signal_type,
            rssi=d.rssi,
            estimated_zone=d.estimated_zone,
            last_seen=d.detected_at,
            is_spike=spike,
            scanner_id=d.scanner_id,
            camera_id=pos.get("camera_id"),
            norm_pos=pos.get("norm_pos"),
        )
    return list(seen.values())
