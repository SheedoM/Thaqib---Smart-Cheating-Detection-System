from datetime import datetime, timedelta, timezone

from scripts.seed_demo import upsert_assignment
from src.thaqib.db.models.exams import ExamSession
from src.thaqib.db.models.infrastructure import Hall


def test_seed_assignment_links_hall_to_exam_session(db_session, test_institution, invigilator_user):
    hall = Hall(
        institution_id=test_institution.id,
        name="Seed Hall",
        capacity=40,
        status="ready",
    )
    session = ExamSession(
        exam_name="Midterm Exam 2024",
        exam_type="Final",
        scheduled_start=datetime.now(timezone.utc) - timedelta(minutes=30),
        scheduled_end=datetime.now(timezone.utc) + timedelta(hours=2),
        status="scheduled",
        student_count=100,
    )
    db_session.add_all([hall, session])
    db_session.commit()

    upsert_assignment(db_session, session, invigilator_user, hall)
    db_session.refresh(session)

    assert [linked_hall.id for linked_hall in session.halls] == [hall.id]
