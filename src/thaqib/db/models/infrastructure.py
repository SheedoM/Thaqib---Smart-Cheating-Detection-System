"""
Infrastructure models: Institution, Hall, Device.

Ref: SRS §5.1 Data Model, FR-01 (Setup), FR-03 (Hall & Device Management)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .exams import ExamSession
    from .users import User


class Institution(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(String(500))

    # Relationships
    halls: Mapped[List["Hall"]] = relationship(
        "Hall", back_populates="institution", cascade="all, delete-orphan"
    )
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="institution", cascade="all, delete-orphan"
    )


class Hall(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "halls"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[Optional[str]] = mapped_column(String(100))
    floor: Mapped[Optional[str]] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    layout_map: Mapped[Optional[dict]] = mapped_column(JSON)
    image: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="not_ready")
    # SRS FR-03.7: 'ready' when all devices online, 'not_ready' otherwise

    # Relationships
    institution: Mapped["Institution"] = relationship("Institution", back_populates="halls")
    devices: Mapped[List["Device"]] = relationship(
        "Device", back_populates="hall", cascade="all, delete-orphan"
    )
    # SRS §5.2: Hall (M) <-> (N) ExamSession (many-to-many)
    exam_sessions: Mapped[List["ExamSession"]] = relationship(
        "ExamSession", secondary="exam_session_halls", back_populates="halls"
    )


class Device(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "devices"

    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'camera' or 'microphone' — SRS FR-03.2
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Position label + coordinates for spatial mapping
    coverage_area: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    # SRS FR-03.5: 'online', 'offline', 'error', 'maintenance'

    # SRS FR-03.6: periodic health checks need a timestamp
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    hall: Mapped["Hall"] = relationship("Hall", back_populates="devices")
    events: Mapped[List["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="device"
    )
