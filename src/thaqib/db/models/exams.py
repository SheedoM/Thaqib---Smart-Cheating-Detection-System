"""
Exam session and assignment models.

Ref: SRS §5.1 Data Model, FR-04 (Exam Session Management)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .events import Alert, DetectionEvent, GroupEvent
    from .infrastructure import Hall
    from .users import User

# SRS §5.2: Hall (M) <-> (N) ExamSession — many-to-many junction table
# One exam can span multiple halls (FR-04.2)
exam_session_halls = Table(
    "exam_session_halls",
    Base.metadata,
    Column(
        "exam_session_id",
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "hall_id",
        ForeignKey("halls.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ExamSession(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """
    A scheduled or active exam monitoring period.

    SRS FR-04.6 statuses: 'scheduled', 'active', 'completed', 'cancelled'
    """
    __tablename__ = "exam_sessions"

    exam_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_type: Mapped[Optional[str]] = mapped_column(String(50))
    scheduled_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    # 'scheduled', 'active', 'completed', 'cancelled'
    student_count: Mapped[Optional[int]] = mapped_column(Integer)
    configuration: Mapped[Optional[dict]] = mapped_column(JSON)
    # Detection thresholds, sensitivity overrides, etc.
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))

    # Relationships
    halls: Mapped[List["Hall"]] = relationship(
        "Hall", secondary=exam_session_halls, back_populates="exam_sessions"
    )
    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment", back_populates="exam_session", cascade="all, delete-orphan"
    )
    detection_events: Mapped[List["DetectionEvent"]] = relationship(
        "DetectionEvent", back_populates="exam_session", cascade="all, delete-orphan"
    )
    group_events: Mapped[List["GroupEvent"]] = relationship(
        "GroupEvent", back_populates="exam_session", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="exam_session", cascade="all, delete-orphan"
    )


class Assignment(Base, UUIDMixin, TimestampMixin):
    """
    Links an invigilator to an exam session.

    SRS FR-04.5: A referee shall assign one or more invigilators to an exam session.
    """
    __tablename__ = "assignments"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    invigilator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="primary")
    # 'primary' or 'secondary'

    # Relationships
    exam_session: Mapped["ExamSession"] = relationship(
        "ExamSession", back_populates="assignments"
    )
    invigilator: Mapped["User"] = relationship("User", back_populates="assignments")
