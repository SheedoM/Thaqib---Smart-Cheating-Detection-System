"""
Expose all models here so that Alembic can properly autogenerate migrations
by simply importing `from thaqib.db.models import Base`
"""

from .base import Base
from .infrastructure import Institution, Hall, Device
from .users import RefreshToken, User
from .exams import ExamSession, Assignment, exam_session_halls
from .events import DetectionEvent, GroupEvent, Alert
from .audit import AuditLog

__all__ = [
    "Base",
    "Institution",
    "Hall",
    "Device",
    "User",
    "RefreshToken",
    "ExamSession",
    "Assignment",
    "exam_session_halls",
    "DetectionEvent",
    "GroupEvent",
    "Alert",
    "AuditLog",
]
