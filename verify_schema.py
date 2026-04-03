
import uuid
from datetime import datetime
from src.thaqib.db.database import SessionLocal
from src.thaqib.db.models.infrastructure import Institution
from src.thaqib.db.models.users import User
from src.thaqib.db.models.exams import ExamSession
from src.thaqib.db.models.events import Alert

def verify_insertion():
    db = SessionLocal()
    try:
        # Create a test institution if not exists
        inst = db.query(Institution).first()
        if not inst:
            inst = Institution(name="Test University", code="TEST")
            db.add(inst)
            db.commit()
            db.refresh(inst)
        
        # Create a test user
        user = User(
            institution_id=inst.id,
            username=f"testuser_{uuid.uuid4().hex[:6]}",
            password_hash="fakehash",
            full_name="Test User",
            email="test@example.com",
            role="admin"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Create a test exam session
        session = ExamSession(
            exam_name="Test Exam",
            scheduled_start=datetime.now(),
            scheduled_end=datetime.now(),
            status="scheduled"
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        # Create a test alert with new fields
        alert = Alert(
            exam_session_id=session.id,
            alert_type="tier_1",
            status="pending",
            claimed_by=user.id,
            claimed_at=datetime.now()
        )
        db.add(alert)
        db.commit()
        
        print("Success: Data inserted correctly into the new schema!")
        
    finally:
        db.close()

if __name__ == "__main__":
    verify_insertion()
