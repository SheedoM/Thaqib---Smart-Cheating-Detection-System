"""
RF (radio-frequency) device-detection models.

A passive, non-jamming subsystem: ESP32-class scanner nodes report the wireless
devices they hear during an exam. MAC addresses are NEVER stored in the clear —
only a SHA-256 hash, so a device can be matched across sightings without the
system holding a personally-identifying hardware address.

Ref: SYSTEM_ARCHITECTURE.md §16 (RF Device Detection Subsystem).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .infrastructure import Hall
    from .exams import ExamSession
    from .users import User


class RfScanner(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A passive BLE/Wi-Fi scanner node registered to a hall."""

    __tablename__ = "rf_scanners"

    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    # Physical placement label + coordinates (e.g. {"label": "front-left", "x": 0.1, "y": 0.0})
    position: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    # SHA-256 of the node's pre-shared key — never store the key itself.
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    # 'online', 'offline'
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    hall: Mapped["Hall"] = relationship("Hall")
    detections: Mapped[List["RfDetection"]] = relationship(
        "RfDetection", back_populates="scanner", cascade="all, delete-orphan"
    )


class RfDetection(Base, UUIDMixin, TimestampMixin):
    """A single wireless-device sighting reported by a scanner node."""

    __tablename__ = "rf_detections"

    scanner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rf_scanners.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exam_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="SET NULL"), index=True
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # 'ble' or 'wifi'
    # SHA-256 hash of the MAC address — raw MAC is NEVER persisted.
    mac_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(255))
    # Advertised name, e.g. "AirPods Pro" / "Galaxy Buds2" (when broadcast).
    rssi: Mapped[Optional[int]] = mapped_column(Integer)
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    estimated_zone: Mapped[Optional[str]] = mapped_column(String(100))
    # Human-readable zone, e.g. "rows 3-4 (front-left)".
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    scanner: Mapped["RfScanner"] = relationship(
        "RfScanner", back_populates="detections"
    )
    exam_session: Mapped[Optional["ExamSession"]] = relationship("ExamSession")


class RfWhitelistEntry(Base, UUIDMixin, TimestampMixin):
    """A device known to be safe in a given hall (added during the baseline scan)."""

    __tablename__ = "rf_whitelist_entries"

    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mac_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(255))
    device_role: Mapped[str] = mapped_column(String(30), default="baseline")
    # 'tablet', 'earbud', 'camera', 'access_point', 'baseline', ...
    # Strongest RSSI seen for this device during the baseline — used to detect a
    # later "RSSI spike" (a hidden device powering on and moving closer).
    baseline_rssi: Mapped[Optional[int]] = mapped_column(Integer)
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    hall: Mapped["Hall"] = relationship("Hall")
    added_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[added_by]
    )
