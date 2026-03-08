import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, SoftDeleteMixin, UUIDMixin

exam_session_halls = Table(
    "exam_session_halls",
    Base.metadata,
    Column("exam_session_id", ForeignKey("exam_sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("hall_id", ForeignKey("halls.id", ondelete="CASCADE"), primary_key=True)
)

class ExamSession(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "exam_sessions"
    
    exam_name: Mapped[str] = mapped_column(String(255), nullable=False)
    exam_type: Mapped[Optional[str]] = mapped_column(String(50))
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    student_count: Mapped[Optional[int]] = mapped_column(Integer)
    configuration: Mapped[Optional[dict]] = mapped_column(JSON)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    
    halls: Mapped[List["Hall"]] = relationship("Hall", secondary=exam_session_halls, back_populates="exam_sessions")
    assignments: Mapped[List["Assignment"]] = relationship("Assignment", back_populates="exam_session", cascade="all, delete-orphan")
    detection_events: Mapped[List["DetectionEvent"]] = relationship("DetectionEvent", back_populates="exam_session", cascade="all, delete-orphan")
    group_events: Mapped[List["GroupEvent"]] = relationship("GroupEvent", back_populates="exam_session", cascade="all, delete-orphan")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="exam_session", cascade="all, delete-orphan")

class Assignment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "assignments"
    
    exam_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False)
    invigilator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="primary")
    
    exam_session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="assignments")
    invigilator: Mapped["User"] = relationship("User", back_populates="assignments")
