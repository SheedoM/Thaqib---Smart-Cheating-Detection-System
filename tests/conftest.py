import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from src.thaqib.main import app
from src.thaqib.db.database import get_db
from src.thaqib.db.models.base import Base
from src.thaqib.core.security import get_password_hash
from src.thaqib.db.models.users import User
from src.thaqib.db.models.infrastructure import Institution

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
def admin_token_headers(client, admin_user):
    login_data = {
        "username": admin_user.username,
        "password": "securepassword",
    }
    r = client.post("/api/auth/login", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers

@pytest.fixture(scope="function")
def invigilator_token_headers(client, invigilator_user):
    login_data = {
        "username": invigilator_user.username,
        "password": "securepassword",
    }
    r = client.post("/api/auth/login", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers
