"""
University-level read-only aggregation endpoints.

Available to super_admin only. Returns data scoped to the caller's
accessible institution subtree (own institution + children).

  GET /api/overview/summary   — KPIs + is_multi_college flag
  GET /api/overview/colleges  — per-college cards
  GET /api/overview/exams     — running/scheduled exams across subtree
  GET /api/overview/alerts    — live alert feed across subtree
"""

from __future__ import annotations

import uuid
from typing import Any, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.thaqib.db.database import get_db
from src.thaqib.db.models.exams import Assignment, ExamAdminAssignment, ExamSession
from src.thaqib.db.models.events import Alert
from src.thaqib.db.models.infrastructure import Hall, Institution
from src.thaqib.db.models.users import User
from src.thaqib.api.dependencies import RequireRole, get_scope
from src.thaqib.core.scoping import is_multi_college

router = APIRouter()
require_super_admin = RequireRole(["super_admin"])


# ─── /summary ────────────────────────────────────────────────────────────────

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_super_admin),
) -> Any:
    """
    Top-line KPIs for the dashboard header plus `is_multi_college`.
    `is_multi_college` is True when the root institution type is 'university'.
    """
    multi = is_multi_college(db, current_user.institution_id)

    running_exams = (
        db.query(ExamSession)
        .filter(
            ExamSession.institution_id.in_(scope),
            ExamSession.status == "active",
        )
        .count()
    )

    active_alerts = (
        db.query(Alert)
        .join(ExamSession, Alert.exam_session_id == ExamSession.id)
        .filter(
            ExamSession.institution_id.in_(scope),
            Alert.status.in_(["pending", "claimed"]),
        )
        .count()
    )

    # colleges-with-activity: children that have ≥1 active exam
    active_college_ids = set(
        row[0]
        for row in db.query(ExamSession.institution_id)
        .filter(
            ExamSession.institution_id.in_(scope),
            ExamSession.institution_id != current_user.institution_id,
            ExamSession.status == "active",
        )
        .distinct()
        .all()
    )

    return {
        "is_multi_college": multi,
        "running_exams": running_exams,
        "active_alerts": active_alerts,
        "active_colleges": len(active_college_ids),
        "institution_type": db.query(Institution.type)
        .filter(Institution.id == current_user.institution_id)
        .scalar(),
    }


# ─── /colleges ───────────────────────────────────────────────────────────────

@router.get("/colleges")
def list_colleges(
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    current_user: User = Depends(require_super_admin),
) -> Any:
    """
    Per-college cards. For a single-tenant install this returns the one card.
    """
    multi = is_multi_college(db, current_user.institution_id)
    if multi:
        institutions = (
            db.query(Institution)
            .filter(Institution.parent_id == current_user.institution_id)
            .all()
        )
    else:
        institutions = (
            db.query(Institution)
            .filter(Institution.id == current_user.institution_id)
            .all()
        )

    result = []
    for inst in institutions:
        running_exams = (
            db.query(ExamSession)
            .filter(
                ExamSession.institution_id == inst.id,
                ExamSession.status == "active",
            )
            .count()
        )
        active_alerts = (
            db.query(Alert)
            .join(ExamSession, Alert.exam_session_id == ExamSession.id)
            .filter(
                ExamSession.institution_id == inst.id,
                Alert.status.in_(["pending", "claimed"]),
            )
            .count()
        )
        halls_ready = (
            db.query(Hall)
            .filter(
                Hall.institution_id == inst.id,
                Hall.deleted_at.is_(None),
                Hall.status == "ready",
            )
            .count()
        )
        invigilators_online = (
            db.query(Assignment)
            .join(ExamSession, Assignment.exam_session_id == ExamSession.id)
            .filter(
                ExamSession.institution_id == inst.id,
                Assignment.monitoring_started_at.isnot(None),
                Assignment.monitoring_ended_at.is_(None),
            )
            .count()
        )
        result.append({
            "id": str(inst.id),
            "name": inst.name,
            "type": inst.type,
            "logo_url": inst.logo_url,
            "running_exams": running_exams,
            "active_alerts": active_alerts,
            "halls_ready": halls_ready,
            "invigilators_online": invigilators_online,
        })

    return {"colleges": result}


# ─── /exams ──────────────────────────────────────────────────────────────────

@router.get("/exams")
def list_overview_exams(
    status: Optional[str] = Query(None, description="Filter by status e.g. 'active'"),
    college_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_super_admin),
) -> Any:
    """
    Running/scheduled exams across the accessible institution subtree.
    Each row includes the college name and live alert count.
    """
    query = db.query(ExamSession).filter(ExamSession.institution_id.in_(scope))
    if status:
        query = query.filter(ExamSession.status == status)
    if college_id:
        if college_id in scope:
            query = query.filter(ExamSession.institution_id == college_id)
        else:
            return {"exams": []}

    sessions = query.order_by(ExamSession.scheduled_start.desc()).limit(200).all()

    # Build a college name lookup
    inst_map = {
        str(i.id): i.name
        for i in db.query(Institution).filter(Institution.id.in_(scope)).all()
    }

    result = []
    for s in sessions:
        hall_count = len([h for h in s.halls])
        live_alerts = (
            db.query(Alert)
            .filter(
                Alert.exam_session_id == s.id,
                Alert.status.in_(["pending", "claimed"]),
            )
            .count()
        )
        result.append({
            "id": str(s.id),
            "exam_name": s.exam_name,
            "exam_type": s.exam_type,
            "status": s.status,
            "scheduled_start": s.scheduled_start.isoformat() if s.scheduled_start else None,
            "scheduled_end": s.scheduled_end.isoformat() if s.scheduled_end else None,
            "student_count": s.student_count,
            "hall_count": hall_count,
            "active_alerts": live_alerts,
            "institution_id": str(s.institution_id) if s.institution_id else None,
            "college_name": inst_map.get(str(s.institution_id), "—"),
        })

    return {"exams": result}


# ─── /alerts ─────────────────────────────────────────────────────────────────

@router.get("/alerts")
def list_overview_alerts(
    college_id: Optional[uuid.UUID] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    scope = Depends(get_scope),
    _: User = Depends(require_super_admin),
) -> Any:
    """
    Live alert feed across the accessible institution subtree (DB-backed).
    Filterable by college_id.
    """
    query = (
        db.query(Alert)
        .join(ExamSession, Alert.exam_session_id == ExamSession.id)
        .filter(
            ExamSession.institution_id.in_(scope),
            Alert.status.in_(["pending", "claimed"]),
        )
    )
    if college_id:
        if college_id in scope:
            query = query.filter(ExamSession.institution_id == college_id)
        else:
            return {"alerts": []}

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()

    inst_map = {
        str(i.id): i.name
        for i in db.query(Institution).filter(Institution.id.in_(scope)).all()
    }

    result = []
    for a in alerts:
        session = a.exam_session
        result.append({
            "id": str(a.id),
            "alert_type": a.alert_type,
            "status": a.status,
            "exam_session_id": str(a.exam_session_id),
            "exam_name": session.exam_name if session else "—",
            "institution_id": str(session.institution_id) if session and session.institution_id else None,
            "college_name": inst_map.get(str(session.institution_id), "—") if session and session.institution_id else "—",
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "claimed_by": str(a.claimed_by) if a.claimed_by else None,
        })

    return {"alerts": result}
