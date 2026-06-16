import pytest
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

os.environ["APP_ENV"] = "testing"
os.environ["LOG_FORMAT"] = "csv"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-32-characters"
os.environ["INTERNAL_EVENT_TOKEN"] = "test-internal-event-token"
os.environ["STREAM_MANAGER_ENABLED"] = "false"
os.environ["DATABASE_ECHO"] = "false"

from src.thaqib.main import app
from src.thaqib.db.database import get_db
from src.thaqib.db.models.base import Base
from src.thaqib.core.security import get_password_hash
from src.thaqib.db.models.users import User
from src.thaqib.db.models.infrastructure import Institution, Hall
from src.thaqib.db.models.exams import ExamSession

# Setup in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
    
@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_institution(db_session):
    inst = Institution(
        name="Test University",
        code="TEST-UNI"
    )
    db_session.add(inst)
    db_session.commit()
    db_session.refresh(inst)
    return inst

@pytest.fixture(scope="function")
def super_admin_user(db_session, test_institution):
    user = User(
        institution_id=test_institution.id,
        username="super_admin_test",
        password_hash=get_password_hash("securepassword"),
        full_name="Super Admin Test",
        email="superadmin@test.com",
        role="super_admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def admin_user(db_session, test_institution):
    user = User(
        institution_id=test_institution.id,
        username="admin_test",
        password_hash=get_password_hash("securepassword"),
        full_name="Admin Test",
        email="admin@test.com",
        role="admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def invigilator_user(db_session, test_institution):
    user = User(
        institution_id=test_institution.id,
        username="invig_test",
        password_hash=get_password_hash("securepassword"),
        full_name="Invigilator Test",
        email="invig@test.com",
        role="invigilator"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def super_admin_token_headers(client, super_admin_user):
    login_data = {
        "username": super_admin_user.username,
        "password": "securepassword",
    }
    r = client.post("/api/auth/login", data=login_data)
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf_token"]}

@pytest.fixture(scope="function")
def admin_token_headers(client, admin_user):
    login_data = {
        "username": admin_user.username,
        "password": "securepassword",
    }
    r = client.post("/api/auth/login", data=login_data)
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf_token"]}

@pytest.fixture(scope="function")
def invigilator_token_headers(client, invigilator_user):
    login_data = {
        "username": invigilator_user.username,
        "password": "securepassword",
    }
    r = client.post("/api/auth/login", data=login_data)
    assert r.status_code == 200
    return {"X-CSRF-Token": r.json()["csrf_token"]}


# ── Multi-tenant fixtures ─────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def university_institution(db_session):
    """Root university institution."""
    inst = Institution(name="Test University", type="university")
    db_session.add(inst)
    db_session.flush()
    db_session.commit()
    db_session.refresh(inst)
    return inst


@pytest.fixture(scope="function")
def college_a(db_session, university_institution):
    inst = Institution(name="College A", type="college", parent_id=university_institution.id)
    db_session.add(inst)
    db_session.flush()
    db_session.commit()
    db_session.refresh(inst)
    return inst


@pytest.fixture(scope="function")
def college_b(db_session, university_institution):
    inst = Institution(name="College B", type="college", parent_id=university_institution.id)
    db_session.add(inst)
    db_session.flush()
    db_session.commit()
    db_session.refresh(inst)
    return inst


@pytest.fixture(scope="function")
def college_a_id(college_a):
    return college_a.id


@pytest.fixture(scope="function")
def college_b_id(college_b):
    return college_b.id


@pytest.fixture(scope="function")
def child_college_id(college_a):
    return college_a.id


@pytest.fixture(scope="function")
def university_super_admin_user(db_session, university_institution):
    user = User(
        institution_id=university_institution.id,
        username="univ_super_admin",
        password_hash=get_password_hash("securepassword"),
        full_name="University Super Admin",
        email="univ_admin@test.com",
        role="super_admin",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def college_a_admin_user(db_session, college_a):
    user = User(
        institution_id=college_a.id,
        username="college_a_admin",
        password_hash=get_password_hash("securepassword"),
        full_name="College A Admin",
        email="college_a@test.com",
        role="admin",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def college_b_admin_user(db_session, college_b):
    user = User(
        institution_id=college_b.id,
        username="college_b_admin",
        password_hash=get_password_hash("securepassword"),
        full_name="College B Admin",
        email="college_b@test.com",
        role="admin",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _login_headers(client, username: str) -> dict:
    r = client.post("/api/auth/login", data={"username": username, "password": "securepassword"})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}


@pytest.fixture(scope="function")
def university_super_admin_headers(client, university_super_admin_user):
    return _login_headers(client, university_super_admin_user.username)


@pytest.fixture(scope="function")
def college_a_admin_headers(client, college_a_admin_user):
    return _login_headers(client, college_a_admin_user.username)


@pytest.fixture(scope="function")
def college_b_admin_headers(client, college_b_admin_user):
    return _login_headers(client, college_b_admin_user.username)


@pytest.fixture(scope="function")
def college_non_super_admin_user(db_session, college_a):
    """Regular admin (not super_admin) — should be 403 for overview endpoints."""
    user = User(
        institution_id=college_a.id,
        username="college_reg_admin",
        password_hash=get_password_hash("securepassword"),
        full_name="College Regular Admin",
        email="college_reg@test.com",
        role="admin",
        status="active",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def college_admin_headers(client, college_non_super_admin_user):
    """Regular admin (not super_admin) — used in overview tests to verify 403."""
    return _login_headers(client, college_non_super_admin_user.username)


@pytest.fixture(scope="function")
def college_a_hall(db_session, college_a):
    hall = Hall(name="Hall A1", institution_id=college_a.id, capacity=50)
    db_session.add(hall)
    db_session.commit()
    db_session.refresh(hall)
    return hall


@pytest.fixture(scope="function")
def college_b_hall(db_session, college_b):
    hall = Hall(name="Hall B1", institution_id=college_b.id, capacity=50)
    db_session.add(hall)
    db_session.commit()
    db_session.refresh(hall)
    return hall


@pytest.fixture(scope="function")
def college_a_hall_id(college_a_hall):
    return college_a_hall.id


@pytest.fixture(scope="function")
def college_b_hall_id(college_b_hall):
    return college_b_hall.id


@pytest.fixture(scope="function")
def college_b_user_id(college_b_admin_user):
    return college_b_admin_user.id


_NOW = datetime(2026, 6, 10, 9, 0, 0, tzinfo=timezone.utc)
_LATER = datetime(2026, 6, 10, 11, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="function")
def college_a_exam_id(db_session, college_a, college_a_hall):
    """Create a college_a exam directly in the DB to avoid shared-client cookie issues."""
    exam = ExamSession(
        exam_name="College A Exam",
        institution_id=college_a.id,
        scheduled_start=_NOW,
        scheduled_end=_LATER,
        status="scheduled",
    )
    exam.halls.append(college_a_hall)
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)
    return exam.id


@pytest.fixture(scope="function")
def college_b_exam_id(db_session, college_b, college_b_hall):
    """Create a college_b exam directly in the DB to avoid shared-client cookie issues."""
    exam = ExamSession(
        exam_name="College B Exam",
        institution_id=college_b.id,
        scheduled_start=_NOW,
        scheduled_end=_LATER,
        status="scheduled",
    )
    exam.halls.append(college_b_hall)
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)
    return exam.id
