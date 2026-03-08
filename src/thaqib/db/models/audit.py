import uuid
from typing import Optional
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDMixin

class AuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "audit_logs"
    
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    target_id: Mapped[Optional[str]] = mapped_column(String(100)) # ID of the record modified
    details: Mapped[Optional[dict]] = mapped_column(JSON)
    
    user: Mapped["User"] = relationship("User")
