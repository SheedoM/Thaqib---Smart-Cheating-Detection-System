"""
User model.

Ref: SRS §2.1 User Roles, FR-02 (Authentication & Authorization)

Roles:
  - 'admin'        → System Administrator (SRS §2.1.1)
  - 'referee'      → Exam scheduling + control room monitoring (SRS §2.1.2)
  - 'invigilator'  → Physical hall presence, receives PTT instructions (SRS §2.1.3)
"""

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from .infrastructure import Institution
    from .exams import Assignment


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'admin', 'referee', 'invigilator' — SRS §2.1
    ptt_id: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Relationships
    institution: Mapped["Institution"] = relationship("Institution", back_populates="users")
    assignments: Mapped[List["Assignment"]] = relationship(
        "Assignment", back_populates="invigilator", cascade="all, delete-orphan"
    )
