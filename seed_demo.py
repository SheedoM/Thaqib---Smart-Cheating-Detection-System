import uuid
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session

from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.exams import ExamSession, Assignment
from src.thaqib.db.models.infrastructure import Hall
from src.thaqib.db.models.users import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_demo_data():
    db = SessionLocal()
    try:
        # 1. Find Hall 101
        hall_101 = db.query(Hall).filter(Hall.name == "قاعة 101").first()
        if not hall_101:
            logger.error("Hall 101 not found. Please run the initial setup first.")
            return

        # Ensure Hall 101 is ready
        if hall_101.status != "ready":
            hall_101.status = "ready"
            db.add(hall_101)
            logger.info("Set Hall 101 status to 'ready'")

        # 2. Find Invigilator
        invigilator = db.query(User).filter(User.username == "invigilator").first()
        if not invigilator:
            logger.error("User 'invigilator' not found.")
            return

        # 3. Create or Update Exam Session
        exam_name = "اختبار نهائي - مقدمة في علوم الحاسب"
        session = db.query(ExamSession).filter(ExamSession.exam_name == exam_name).first()
        
        now = datetime.now()
        start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
        
        if not session:
            session = ExamSession(
                exam_name=exam_name,
                exam_type="final",
                scheduled_start=start_time,
                scheduled_end=end_time,
                status="scheduled",
                student_count=45,
                configuration={"sensitivity": "high"}
            )
            session.halls.append(hall_101)
            db.add(session)
            db.flush() # Get session ID
            logger.info(f"Created exam session: {exam_name}")
        else:
            session.scheduled_start = start_time
            session.scheduled_end = end_time
            if hall_101 not in session.halls:
                session.halls.append(hall_101)
            logger.info(f"Updated existing exam session: {exam_name}")

        # 4. Reset ALL existing monitoring statuses for a fresh demo start
        db.query(Assignment).update({
            Assignment.monitoring_started_at: None,
            Assignment.monitoring_ended_at: None
        })
        logger.info("Reset all previous assignment monitoring statuses")

        # 5. Create or Update Assignment for Hall 101
        assignment = db.query(Assignment).filter(
            Assignment.exam_session_id == session.id,
            Assignment.hall_id == hall_101.id
        ).first()

        if not assignment:
            assignment = Assignment(
                exam_session_id=session.id,
                invigilator_id=invigilator.id,
                hall_id=hall_101.id,
                role="primary"
            )
            db.add(assignment)
            logger.info(f"Assigned 'invigilator' to Hall 101 for session: {exam_name}")
        else:
            assignment.invigilator_id = invigilator.id
            assignment.role = "primary"
            logger.info(f"Updated assignment for 'invigilator' in Hall 101")

        # 6. Ensure session is scheduled (not active yet)
        session.status = "scheduled"
        session.actual_start = None
        session.actual_end = None


        db.commit()
        logger.info("Demo seeding completed successfully.")

    except Exception as e:
        db.rollback()
        logger.exception(f"Error seeding demo data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_data()
