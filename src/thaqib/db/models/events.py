import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime, JSON, DECIMAL, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDMixin

class GroupEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "group_events"
    
    exam_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    student_positions: Mapped[dict] = mapped_column(JSON, nullable=False) # Array of positions
    
    exam_session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="group_events")
    detection_events: Mapped[List["DetectionEvent"]] = relationship("DetectionEvent", back_populates="group_event")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="group_event")

class DetectionEvent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "detection_events"
    
    exam_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("devices.id"))
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("group_events.id", ondelete="SET NULL"))
    
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    student_position: Mapped[dict] = mapped_column(JSON, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(DECIMAL(3, 2))
    
    video_url: Mapped[Optional[str]] = mapped_column(String(500))
    audio_url: Mapped[Optional[str]] = mapped_column(String(500))
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    
    exam_session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="detection_events")
    device: Mapped["Device"] = relationship("Device", back_populates="events")
    group_event: Mapped["GroupEvent"] = relationship("GroupEvent", back_populates="detection_events")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="detection_event")

class Alert(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "alerts"
    
    exam_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False)
    detection_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("detection_events.id"))
    group_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("group_events.id"))
    
    alert_type: Mapped[str] = mapped_column(String(10), nullable=False) # tier_1, tier_2
    status: Mapped[str] = mapped_column(String(20), default="pending")
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"))
    
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[Optional[str]] = mapped_column(String(1000))
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    exam_session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="alerts")
    detection_event: Mapped["DetectionEvent"] = relationship("DetectionEvent", back_populates="alerts")
    group_event: Mapped["GroupEvent"] = relationship("GroupEvent", back_populates="alerts")
    assigned_user: Mapped["User"] = relationship("User")
