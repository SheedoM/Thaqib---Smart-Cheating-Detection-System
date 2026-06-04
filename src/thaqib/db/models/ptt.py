"""
Push-to-talk channel evidence models.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .events import Alert
    from .exams import ExamSession
    from .infrastructure import Hall, HallVoiceChannel
    from .users import User


class PttClip(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "ptt_clips"

    exam_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False
    )
    hall_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("halls.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hall_voice_channels.id", ondelete="CASCADE"), nullable=False
    )
    speaker_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    speaker_role: Mapped[str] = mapped_column(String(20), nullable=False)
    speaker_name: Mapped[str] = mapped_column(String(255), nullable=False)
    clip_type: Mapped[str] = mapped_column(String(20), default="normal")
    alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("alerts.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    audio_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)

    exam_session: Mapped["ExamSession"] = relationship("ExamSession", back_populates="ptt_clips")
    hall: Mapped["Hall"] = relationship("Hall", back_populates="ptt_clips")
    channel: Mapped["HallVoiceChannel"] = relationship(
        "HallVoiceChannel", back_populates="ptt_clips"
    )
    speaker: Mapped["User"] = relationship("User", back_populates="ptt_clips")
    alert: Mapped[Optional["Alert"]] = relationship("Alert")
