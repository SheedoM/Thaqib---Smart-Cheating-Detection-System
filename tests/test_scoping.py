"""
Unit tests for src.thaqib.core.scoping — tenant scoping primitives.
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from src.thaqib.core.scoping import accessible_institution_ids, is_multi_college
from src.thaqib.db.models.infrastructure import Institution


# ── helpers ──────────────────────────────────────────────────────────────────

def make_institution(db: Session, name: str, type_: str = "college", parent_id=None) -> Institution:
    inst = Institution(name=name, type=type_, parent_id=parent_id)
    db.add(inst)
    db.flush()
    return inst


# ── accessible_institution_ids ────────────────────────────────────────────────

class TestAccessibleInstitutionIds:
    def test_leaf_institution_returns_only_self(self, db_session: Session):
        college = make_institution(db_session, "College A", "college")
        db_session.commit()

        result = accessible_institution_ids(db_session, college.id)
        assert result == {college.id}

    def test_university_includes_self_and_children(self, db_session: Session):
        university = make_institution(db_session, "University", "university")
        c1 = make_institution(db_session, "College 1", "college", parent_id=university.id)
        c2 = make_institution(db_session, "College 2", "college", parent_id=university.id)
        db_session.commit()

        result = accessible_institution_ids(db_session, university.id)
        assert university.id in result
        assert c1.id in result
        assert c2.id in result
        assert len(result) == 3

    def test_college_does_not_see_siblings(self, db_session: Session):
        university = make_institution(db_session, "University", "university")
        c1 = make_institution(db_session, "College 1", "college", parent_id=university.id)
        c2 = make_institution(db_session, "College 2", "college", parent_id=university.id)
        db_session.commit()

        result = accessible_institution_ids(db_session, c1.id)
        assert c1.id in result
        assert c2.id not in result
        assert university.id not in result

    def test_college_does_not_see_parent_university(self, db_session: Session):
        university = make_institution(db_session, "University", "university")
        c1 = make_institution(db_session, "College 1", "college", parent_id=university.id)
        db_session.commit()

        result = accessible_institution_ids(db_session, c1.id)
        assert university.id not in result

    def test_standalone_returns_only_self(self, db_session: Session):
        standalone = make_institution(db_session, "School", "standalone")
        db_session.commit()

        result = accessible_institution_ids(db_session, standalone.id)
        assert result == {standalone.id}

    def test_unknown_id_returns_set_with_that_id(self, db_session: Session):
        # Even if the institution doesn't exist, the id itself is included
        fake_id = uuid.uuid4()
        result = accessible_institution_ids(db_session, fake_id)
        assert fake_id in result


# ── is_multi_college ──────────────────────────────────────────────────────────

class TestIsMultiCollege:
    def test_university_returns_true(self, db_session: Session):
        univ = make_institution(db_session, "University", "university")
        db_session.commit()
        assert is_multi_college(db_session, univ.id) is True

    def test_college_returns_false(self, db_session: Session):
        college = make_institution(db_session, "College", "college")
        db_session.commit()
        assert is_multi_college(db_session, college.id) is False

    def test_standalone_returns_false(self, db_session: Session):
        sa = make_institution(db_session, "Standalone", "standalone")
        db_session.commit()
        assert is_multi_college(db_session, sa.id) is False

    def test_unknown_id_returns_false(self, db_session: Session):
        assert is_multi_college(db_session, uuid.uuid4()) is False
