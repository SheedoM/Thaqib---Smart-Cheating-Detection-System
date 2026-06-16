"""
RF device-detection logic: hashing, zone estimation, whitelist/baseline
handling, RSSI-spike detection, and alert creation.

Design note — this subsystem deliberately reuses the existing
DetectionEvent → Alert path (no new alerting machinery). An RF hit becomes a
DetectionEvent(event_type="rf_transmission") plus a tier-2 Alert, exactly like a
gaze or audio incident, so it flows through the same dashboard and reporting code.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.exams import ExamSession, exam_session_halls
from src.thaqib.db.models.rf import RfDetection, RfScanner, RfWhitelistEntry

logger = logging.getLogger(__name__)

# An RSSI increase (device moved closer / powered up) of this many dB above the
# whitelisted baseline re-flags an otherwise-known device — the classic "hidden
# earbud just switched on" signature.
RF_SPIKE_DB = 15
# Default pre-exam baseline window.
BASELINE_SECONDS = 300

# In-memory baseline windows: hall_id (str) -> datetime the baseline closes.
# In-process state only, mirroring the stateless voice channel; nothing to persist.
_baseline_until: dict[str, datetime] = {}
_baseline_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_mac(mac: str) -> str:
    """SHA-256 of a normalized MAC. The raw MAC is never stored."""
    normalized = mac.strip().lower().replace("-", ":")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def estimate_zone(scanner: RfScanner, rssi: int | None) -> str:
    """Estimate a human-readable zone from the reporting node and signal strength."""
    label = "unknown area"
    if scanner.position and isinstance(scanner.position, dict):
        label = str(scanner.position.get("label") or label)
    if rssi is None:
        return f"{label}"
    if rssi >= -60:
        proximity = "very close to"
    elif rssi >= -75:
        proximity = "near"
    else:
        proximity = "in the wider area of"
    return f"{proximity} {label}"


def start_baseline(hall_id: uuid.UUID, seconds: int = BASELINE_SECONDS) -> datetime:
    """Open a baseline window for a hall; devices heard during it are whitelisted."""
    until = _now() + timedelta(seconds=seconds)
    with _baseline_lock:
        _baseline_until[str(hall_id)] = until
    logger.info("RF baseline opened for hall %s until %s", hall_id, until.isoformat())
    return until


def baseline_active(hall_id: uuid.UUID) -> bool:
    with _baseline_lock:
        until = _baseline_until.get(str(hall_id))
    return bool(until and until > _now())


def active_session_id_for_hall(db: Session, hall_id: uuid.UUID) -> uuid.UUID | None:
    """Return the id of the active exam session covering this hall, if any."""
    stmt = (
        select(ExamSession.id)
        .join(exam_session_halls, exam_session_halls.c.exam_session_id == ExamSession.id)
        .where(
            exam_session_halls.c.hall_id == hall_id,
            ExamSession.status == "active",
            ExamSession.deleted_at.is_(None),
        )
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _upsert_whitelist(db: Session, hall_id: uuid.UUID, mac_hash: str, name: str | None, rssi: int | None) -> bool:
    """Add or strengthen a baseline whitelist entry. Returns True if newly added."""
    entry = (
        db.query(RfWhitelistEntry)
        .filter(RfWhitelistEntry.hall_id == hall_id, RfWhitelistEntry.mac_hash == mac_hash)
        .first()
    )
    if entry is None:
        db.add(
            RfWhitelistEntry(
                hall_id=hall_id,
                mac_hash=mac_hash,
                device_name=name,
                device_role="baseline",
                baseline_rssi=rssi,
            )
        )
        return True
    # Keep the strongest (closest) RSSI seen during baseline as the reference.
    if rssi is not None and (entry.baseline_rssi is None or rssi > entry.baseline_rssi):
        entry.baseline_rssi = rssi
    if name and not entry.device_name:
        entry.device_name = name
    return False


def process_detections(db: Session, scanner: RfScanner, sightings) -> dict:
    """Record sightings and, when appropriate, raise alerts.

    Returns a summary dict plus a list of alert payloads for the route to push
    live to the dashboard / hall voice channel.
    """
    hall_id = scanner.hall_id
    in_baseline = baseline_active(hall_id)
    session_id = None if in_baseline else active_session_id_for_hall(db, hall_id)

    # Preload the hall whitelist once.
    wl = {
        e.mac_hash: e
        for e in db.query(RfWhitelistEntry).filter(RfWhitelistEntry.hall_id == hall_id).all()
    }

    recorded = 0
    whitelisted_added = 0
    alert_payloads: list[dict] = []

    for s in sightings:
        mac_hash = hash_mac(s.mac)
        name = s.name
        rssi = s.rssi
        seen_at = s.seen_at or _now()

        if in_baseline:
            if _upsert_whitelist(db, hall_id, mac_hash, name, rssi):
                whitelisted_added += 1
            # During baseline we still log the sighting but never alert.
            db.add(RfDetection(
                scanner_id=scanner.id, exam_session_id=None, detected_at=seen_at,
                signal_type=s.signal_type, mac_hash=mac_hash, device_name=name,
                rssi=rssi, is_whitelisted=True, estimated_zone=estimate_zone(scanner, rssi),
                metadata_json={"phase": "baseline"},
            ))
            recorded += 1
            continue

        known = wl.get(mac_hash)
        is_whitelisted = known is not None
        # Spike = a whitelisted device suddenly much closer than its baseline.
        is_spike = bool(
            is_whitelisted and rssi is not None and known.baseline_rssi is not None
            and (rssi - known.baseline_rssi) >= RF_SPIKE_DB
        )
        alertable = (not is_whitelisted) or is_spike
        zone = estimate_zone(scanner, rssi)

        detection = RfDetection(
            scanner_id=scanner.id, exam_session_id=session_id, detected_at=seen_at,
            signal_type=s.signal_type, mac_hash=mac_hash, device_name=name, rssi=rssi,
            is_whitelisted=is_whitelisted, estimated_zone=zone,
            metadata_json={"spike": is_spike} if is_spike else None,
        )
        db.add(detection)
        recorded += 1

        if alertable and session_id is not None:
            payload = _raise_rf_alert(db, scanner, session_id, name, zone, s.signal_type, rssi, is_spike)
            if payload:
                alert_payloads.append(payload)

    scanner.last_seen = _now()
    scanner.status = "online"
    db.commit()

    return {
        "recorded": recorded,
        "alerts_raised": len(alert_payloads),
        "baseline_active": in_baseline,
        "whitelisted_added": whitelisted_added,
        "alert_payloads": alert_payloads,
    }


def _raise_rf_alert(db, scanner, session_id, name, zone, signal_type, rssi, is_spike) -> dict | None:
    """Create a DetectionEvent + tier-2 Alert for an RF hit (reuses the alert path)."""
    label = name or ("device" if not is_spike else "hidden device")
    reason = "signal spike (device powered on / moved closer)" if is_spike else "unrecognized device"
    try:
        event = DetectionEvent(
            exam_session_id=session_id,
            device_id=None,
            event_type="rf_transmission",
            severity="high",
            student_position={"zone": zone, "scanner": scanner.identifier},
            timestamp=_now(),
            confidence_score=None,
            metadata_json={
                "device_name": name,
                "signal_type": signal_type,
                "rssi": rssi,
                "estimated_zone": zone,
                "is_spike": is_spike,
                "reason": reason,
                "hall_id": str(scanner.hall_id),
            },
        )
        alert = Alert(
            exam_session_id=session_id,
            detection_event=event,
            alert_type="tier_2",
            status="pending",
        )
        db.add(alert)
        db.flush()  # assign ids without ending the outer transaction
        logger.warning("RF ALERT: %s — %s (%s)", label, zone, reason)
        return {
            "id": str(alert.id),
            "exam_session_id": str(session_id),
            "hall_id": str(scanner.hall_id),
            "event_type": "rf_transmission",
            "severity": "high",
            "device_name": name,
            "signal_type": signal_type,
            "rssi": rssi,
            "estimated_zone": zone,
            "is_spike": is_spike,
            "reason": reason,
            "timestamp": event.timestamp.isoformat(),
            "location": zone,
        }
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to raise RF alert: %s", exc)
        return None
