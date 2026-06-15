from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session, selectinload

from src.thaqib.db.models.audit import AuditLog
from src.thaqib.db.models.events import Alert, DetectionEvent
from src.thaqib.db.models.users import User

NORMAL_REVIEW_RETENTION_DAYS = 180
CANCELLED_RETENTION_DAYS = 30
CONFIRMED_RETENTION_YEARS = 3


@dataclass
class EvidencePurgeResult:
    purged_count: int = 0
    purged_alert_ids: list[str] = field(default_factory=list)
    deleted_files: list[str] = field(default_factory=list)
    skipped_held_count: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(month=2, day=28, year=value.year + years)


def retention_deadline_for_alert(alert: Alert, now: datetime | None = None) -> datetime:
    now = now or _now()
    if alert.status == "confirmed":
        return add_years(alert.confirmed_at or now, CONFIRMED_RETENTION_YEARS)
    if alert.status in {"cancelled", "false_positive"}:
        return (alert.cancelled_at or alert.resolved_at or now) + timedelta(days=CANCELLED_RETENTION_DAYS)
    return (alert.created_at or now) + timedelta(days=NORMAL_REVIEW_RETENTION_DAYS)


def apply_alert_retention(alert: Alert, now: datetime | None = None) -> None:
    alert.evidence_retention_until = retention_deadline_for_alert(alert, now)


def place_legal_hold(
    db: Session,
    alert: Alert,
    user: User,
    reason: str,
    now: datetime | None = None,
) -> None:
    now = now or _now()
    alert.legal_hold = True
    alert.legal_hold_reason = reason
    alert.legal_hold_by = user.id
    alert.legal_hold_at = now
    db.add(
        AuditLog(
            action_type="evidence_legal_hold_placed",
            user_id=user.id,
            target_id=str(alert.id),
            details={"reason": reason, "exam_session_id": str(alert.exam_session_id)},
        )
    )


def release_legal_hold(
    db: Session,
    alert: Alert,
    user: User,
    now: datetime | None = None,
) -> None:
    now = now or _now()
    previous_reason = alert.legal_hold_reason
    alert.legal_hold = False
    alert.legal_hold_reason = None
    alert.legal_hold_by = None
    alert.legal_hold_at = None
    db.add(
        AuditLog(
            action_type="evidence_legal_hold_released",
            user_id=user.id,
            target_id=str(alert.id),
            details={
                "previous_reason": previous_reason,
                "released_at": now.isoformat(),
                "exam_session_id": str(alert.exam_session_id),
            },
        )
    )


def _resolve_evidence_file(alerts_dir: Path, rel_path: str | None) -> Path | None:
    if not rel_path:
        return None
    root = alerts_dir.resolve()
    candidate = (root / Path(rel_path)).resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def _delete_if_present(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    path.unlink()
    return str(path)


def _purge_detection_event_files(event: DetectionEvent, alerts_dir: Path) -> list[str]:
    deleted: list[str] = []
    for rel_path in (event.video_clip_path, event.audio_clip_path):
        deleted_path = _delete_if_present(_resolve_evidence_file(alerts_dir, rel_path))
        if deleted_path:
            deleted.append(deleted_path)

    metadata = dict(event.metadata_json or {})
    snapshot = metadata.get("snapshot_file")
    deleted_path = _delete_if_present(_resolve_evidence_file(alerts_dir, snapshot))
    if deleted_path:
        deleted.append(deleted_path)

    event.video_clip_path = None
    event.audio_clip_path = None
    if "snapshot_file" in metadata:
        metadata["snapshot_file"] = None
        event.metadata_json = metadata
    return deleted


def purge_expired_alert_evidence(
    db: Session,
    *,
    alerts_dir: Path,
    now: datetime | None = None,
    limit: int = 100,
) -> EvidencePurgeResult:
    now = now or _now()
    result = EvidencePurgeResult(
        skipped_held_count=db.query(Alert)
        .filter(
            Alert.evidence_retention_until.is_not(None),
            Alert.evidence_retention_until <= now,
            Alert.legal_hold.is_(True),
            Alert.evidence_purged_at.is_(None),
        )
        .count()
    )
    expired_alerts = (
        db.query(Alert)
        .options(selectinload(Alert.detection_event))
        .filter(
            Alert.evidence_retention_until.is_not(None),
            Alert.evidence_retention_until <= now,
            Alert.legal_hold.is_(False),
            Alert.evidence_purged_at.is_(None),
        )
        .order_by(Alert.evidence_retention_until)
        .limit(limit)
        .all()
    )

    for alert in expired_alerts:
        deleted_files: list[str] = []
        if alert.detection_event is not None:
            deleted_files = _purge_detection_event_files(alert.detection_event, alerts_dir)
            result.deleted_files.extend(deleted_files)
        alert.evidence_purged_at = now
        result.purged_alert_ids.append(str(alert.id))
        db.add(
            AuditLog(
                action_type="evidence_purged",
                user_id=None,
                target_id=str(alert.id),
                details={
                    "exam_session_id": str(alert.exam_session_id),
                    "retention_until": alert.evidence_retention_until.isoformat()
                    if alert.evidence_retention_until
                    else None,
                    "deleted_files": deleted_files,
                },
            )
        )

    result.purged_count = len(result.purged_alert_ids)
    db.commit()
    return result
