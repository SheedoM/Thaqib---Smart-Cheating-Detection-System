"""
Institution scoping: compute the set of institution IDs a user may access.

Depth is capped at 2 (university → college). A user always has access to
their own institution plus any direct children (colleges).

  - Single-tenant (college/school/standalone): returns {own_id}
  - University super admin: returns {university_id} ∪ {all college ids}
"""

from __future__ import annotations

import uuid
from typing import Set

from sqlalchemy.orm import Session

from src.thaqib.db.models.infrastructure import Institution


def accessible_institution_ids(db: Session, user_institution_id: uuid.UUID) -> Set[uuid.UUID]:
    """Return all institution IDs reachable from *user_institution_id* (self + children)."""
    result: Set[uuid.UUID] = {user_institution_id}
    # Direct children (depth-1 only; cap at 2 total levels: university → college)
    children = (
        db.query(Institution.id)
        .filter(Institution.parent_id == user_institution_id)
        .all()
    )
    result |= {row[0] for row in children}
    return result


def is_multi_college(db: Session, institution_id: uuid.UUID) -> bool:
    """True when the institution type is 'university' (regardless of child count)."""
    row = db.query(Institution.type).filter(Institution.id == institution_id).first()
    return bool(row and row[0] == "university")
