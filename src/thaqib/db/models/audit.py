"""
Audit log model.

Ref: SRS NFR-02.6 — All user actions shall be tracked in an audit log.
"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .users import User


class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # e.g., 'user_login', 'session_created', 'alert_claimed', 'device_registered'
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    target_id: Mapped[Optional[str]] = mapped_column(String(100))
    # ID of the record that was modified
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User")
