import os
import sys
import uuid

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.thaqib.main import app
from src.thaqib.db.database import get_db
from src.thaqib.db.models.base import Base
from src.thaqib.api.dependencies import get_current_user
from src.thaqib.db.models.users import User

# Setup test DB
db_path = "./test_api_verification.db"
if os.path.exists(db_path):
    os.remove(db_path)
    
SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Mock passlib to avoid bcrypt > 4.0 "72 bytes" initialization crash during tests
import src.thaqib.core.security
src.thaqib.core.security.get_password_hash = lambda pwd: pwd + "_hashed"

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Mock the current user dependency to always return an admin
def override_get_current_user():
    return User(
        id=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"), 
        username="admin",
        full_name="System Admin",
        email="admin@test.com", 
        role="admin", 
        status="active",
        institution_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174001")
    )

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

def run_tests():
    print("Running API Integration Tests...\n")
    
    # ------------- Institutions -------------
    print("--- Testing Institutions API ---")
    response = client.post("/api/institutions/", json={
        "name": "Test University",
        "contact_email": "admin@testuni.edu",
        "domain": "testuni.edu",
        "status": "active"
    })
    print(f"POST /api/institutions/: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"
    inst_id = response.json()["id"]

    response = client.get("/api/institutions/")
    print(f"GET /api/institutions/: {response.status_code}")
    assert response.status_code == 200

    # ------------- Halls -------------
    print("\n--- Testing Halls API ---")
    response = client.post("/api/halls/", json={
        "name": "Main Hall",
        "capacity": 100,
        "type": "exam",
        "institution_id": inst_id
    })
    print(f"POST /api/halls/: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"
    hall_id = response.json()["id"]

    response = client.get(f"/api/halls/?institution_id={inst_id}")
    print(f"GET /api/halls/: {response.status_code}")
    assert response.status_code == 200

    # ------------- Users -------------
    print("\n--- Testing Users API ---")
    response = client.post("/api/users/", json={
        "username": "invigilator1",
        "email": "invigilator@testuni.edu",
        "password": "securepassword123",
        "full_name": "John Doe",
        "role": "invigilator",
        "institution_id": inst_id
    })
    print(f"POST /api/users/: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"
    user_id = response.json()["id"]

    # ------------- Devices -------------
    print("\n--- Testing Devices API ---")
    response = client.post("/api/devices/", json={
        "hall_id": hall_id,
        "identifier": "CAM-101",
        "type": "camera",
        "stream_url": "rtsp://camera_ip/stream1",
        "ip_address": "192.168.1.100",
        "mac_address": "00:1B:44:11:3A:B7",
        "position": {"x": 10, "y": 20},
        "status": "online",
        "device_metadata": {"resolution": "1080p"}
    })
    print(f"POST /api/devices/: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"
    device_id = response.json()["id"]

    # ------------- Exam Sessions -------------
    print("\n--- Testing Exam Sessions API ---")
    response = client.post("/api/sessions/", json={
        "course_code": "CS101",
        "exam_name": "Intro to CS",
        "scheduled_start": "2026-03-27T08:00:00Z",
        "scheduled_end": "2026-03-27T10:00:00Z",
        "institution_id": inst_id,
        "hall_ids": [hall_id]
    })
    print(f"POST /api/sessions/: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"
    exam_id = response.json()["id"]

    response = client.post(f"/api/sessions/{exam_id}/assignments", json={
        "invigilator_id": user_id,
        "role": "primary",
        "hall_id": hall_id
    })
    print(f"POST /api/sessions/{{id}}/assignments: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"

    # ------------- Events -------------
    print("\n--- Testing Detection Events API (US-308) ---")
    response = client.post("/api/events/", json={
        "exam_session_id": exam_id,
        "device_id": device_id,
        "event_type": "head_pose",
        "severity": "medium",
        "student_position": {"seat": "A1"},
        "timestamp": "2026-03-26T17:50:00Z",
        "confidence_score": 0.85
    })
    print(f"POST /api/events/: {response.status_code}")
    assert response.status_code == 201, f"Failed: {response.text}"

    print("\nSUCCESS: All APIs responded correctly. Verification successful!")

if __name__ == '__main__':
    run_tests()
    
    # Cleanup
    try:
        os.remove("./test_api_verification.db")
    except Exception:
        pass
