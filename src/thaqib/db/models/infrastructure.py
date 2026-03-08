import uuid
from typing import List, Optional
from sqlalchemy import String, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, SoftDeleteMixin, UUIDMixin

class Institution(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "institutions"
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    
    halls: Mapped[List["Hall"]] = relationship("Hall", back_populates="institution", cascade="all, delete-orphan")
    users: Mapped[List["User"]] = relationship("User", back_populates="institution", cascade="all, delete-orphan")

class Hall(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "halls"
    
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    building: Mapped[Optional[str]] = mapped_column(String(100))
    floor: Mapped[Optional[str]] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    layout_map: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="not_ready")
    
    institution: Mapped["Institution"] = relationship("Institution", back_populates="halls")
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="hall", cascade="all, delete-orphan")
    exam_sessions: Mapped[List["ExamSession"]] = relationship("ExamSession", secondary="exam_session_halls", back_populates="halls")

class Device(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "devices"
    
    hall_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("halls.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False) # 'camera' or 'microphone'
    identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    stream_url: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[dict] = mapped_column(JSON, nullable=False)
    coverage_area: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="offline")
    
    hall: Mapped["Hall"] = relationship("Hall", back_populates="devices")
    events: Mapped[List["DetectionEvent"]] = relationship("DetectionEvent", back_populates="device")
