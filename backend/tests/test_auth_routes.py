import pytest
from fastapi.testclient import TestClient
from sqlalchemy.future import select

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_register_success(client: TestClient):
    payload = {
        "name": "API User",
        "email": "apiuser@example.com",
        "password": "securepassword123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["name"] == "API User"
    assert data["email"] == "apiuser@example.com"
    assert "password" not in data
    assert "password_hash" not in data
    assert "id" in data
    assert data["is_active"] is True

def test_register_duplicate(client: TestClient):
    payload = {
        "name": "Duplicate API User",
        "email": "apiduplicate@example.com",
        "password": "securepassword123"
    }
    # First request
    response1 = client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 201
    
    # Second request
    response2 = client.post("/api/v1/auth/register", json=payload)
    assert response2.status_code == 409
    assert response2.json()["detail"] == "A user with this email already exists."

def test_login_success(client: TestClient):
    payload = {
        "name": "Login Test User",
        "email": "apilogin@example.com",
        "password": "securepassword123"
    }
    client.post("/api/v1/auth/register", json=payload)
    
    login_payload = {
        "email": "apilogin@example.com",
        "password": "securepassword123"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client: TestClient):
    login_payload = {
        "email": "unknown@example.com",
        "password": "wrongpassword"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

def test_login_inactive(client: TestClient):
    payload = {
        "name": "Inactive API User",
        "email": "apiinactive@example.com",
        "password": "securepassword123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    
    import uuid
    user_id = uuid.UUID(response.json()["id"])
    
    # Manually set user to inactive
    with get_sync_session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one()
        user.is_active = False
        session.commit()
        
    login_payload = {
        "email": "apiinactive@example.com",
        "password": "securepassword123"
    }
    response = client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "User is inactive"

def test_register_malformed_payload(client: TestClient):
    payload = {
        "name": "Malformed User",
        "email": "not-an-email",
        "password": "secure"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422

def test_read_users_me(client: TestClient):
    payload = {
        "name": "Me User",
        "email": "me@example.com",
        "password": "securepassword123"
    }
    client.post("/api/v1/auth/register", json=payload)
    
    login_payload = {
        "email": "me@example.com",
        "password": "securepassword123"
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    token = login_res.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "me@example.com"
    assert me_res.json()["name"] == "Me User"

def test_read_users_me_unauthorized(client: TestClient):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

