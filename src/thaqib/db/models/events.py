"""
Detection events, group events, and alerts.

Ref: SRS §5.1 Data Model, FR-08 (Alert Processing & Shared Queue)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, DECIMAL, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .exams import ExamSession
    from .infrastructure import Device
    from .users import User


class GroupEvent(Base, UUIDMixin, TimestampMixin):
    """
    Multiple correlated detection events grouped together.

    SRS FR-08.3: If multiple students are involved in related events,
    the system shall create a group event.
    """
    __tablename__ = "group_events"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g., 'neighbor_cheating', 'coordinated_gaze'
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'low', 'medium', 'high'
    student_positions: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Array of involved student seat positions

    # Relationships
    exam_session: Mapped["ExamSession"] = relationship(
        "ExamSession", back_populates="group_events"
    )
    detection_events: Mapped[List["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="group_event"
    )
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="group_event")


class DetectionEvent(Base, UUIDMixin, TimestampMixin):
    """
    A single AI-detected suspicious behavior.

    SRS FR-08.1: The system shall create a detection event record
    for each suspicious behavior detected (gaze, audio, object).
    """
    __tablename__ = "detection_events"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("devices.id"))
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("group_events.id", ondelete="SET NULL")
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'head_pose', 'gaze_alignment', 'audio_anomaly', 'object_detected'
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'low', 'medium', 'high'
    student_position: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Seat number/position identifier
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(DECIMAL(3, 2))

    video_clip_path: Mapped[Optional[str]] = mapped_column(String(500))
    # Short auto-expiring clip — SRS NFR-02.4
    audio_clip_path: Mapped[Optional[str]] = mapped_column(String(500))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    # Flexible metadata: head pose angles, gaze vectors, confidence breakdown, etc.

    # Relationships
    exam_session: Mapped["ExamSession"] = relationship(
        "ExamSession", back_populates="detection_events"
    )
    device: Mapped[Optional["Device"]] = relationship("Device", back_populates="events")
    group_event: Mapped[Optional["GroupEvent"]] = relationship(
        "GroupEvent", back_populates="detection_events"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="detection_event"
    )


class Alert(Base, UUIDMixin, TimestampMixin):
    """
    A notification generated for referee review in the shared alert queue.

    SRS FR-08.7 lifecycle: pending → claimed → (resolved / false_positive / escalated)
    SRS §2.2: Shared Alert Queue — referee claims alerts, no pre-assignment.
    """
    __tablename__ = "alerts"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    detection_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("detection_events.id")
    )
    group_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("group_events.id")
    )
    # SRS §5.2: Alert → DetectionEvent (1) XOR GroupEvent (1)
    # Enforced at application level: exactly one must be non-null

    alert_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # 'tier_1' or 'tier_2' — SRS FR-08.4

    status: Mapped[str] = mapped_column(String(20), default="pending")
    # SRS FR-08.7: 'pending', 'claimed', 'resolved', 'false_positive', 'escalated'

    # Shared Alert Queue: referee claims the alert (not pre-assigned)
    claimed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[Optional[str]] = mapped_column(String(1000))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    exam_session: Mapped["ExamSession"] = relationship(
        "ExamSession", back_populates="alerts"
    )
    detection_event: Mapped[Optional["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="alerts"
    )
    group_event: Mapped[Optional["GroupEvent"]] = relationship(
        "GroupEvent", back_populates="alerts"
    )
    claimed_user: Mapped[Optional["User"]] = relationship("User")
