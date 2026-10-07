import pytest
from fastapi.testclient import TestClient
from sqlalchemy.future import select

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def get_auth_headers(client: TestClient, role: UserRole) -> dict:
    email = f"rbac_{role.value.lower()}@example.com"
    payload = {
        "name": f"User {role.value}",
        "email": email,
        "password": "securepassword123"
    }
    client.post("/api/v1/auth/register", json=payload)
    
    # Force role update in DB
    with get_sync_session() as session:
        user = session.execute(select(User).where(User.email == email)).scalar_one()
        user.role = role
        session.commit()
        
    login_payload = {
        "email": email,
        "password": "securepassword123"
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("role,expected_status", [
    (UserRole.SUPER_ADMIN, 200),
    (UserRole.ORGANIZATION_ADMIN, 403),
    (UserRole.SITE_MANAGER, 403),
    (UserRole.STATION_OPERATOR, 403),
    (UserRole.TECHNICIAN, 403),
    (UserRole.VIEWER, 403),
    (UserRole.OWNER, 403),
    (UserRole.FAMILY_MEMBER, 403)
])
def test_super_admin_endpoint(client: TestClient, role: UserRole, expected_status: int):
    headers = get_auth_headers(client, role)
    response = client.get("/api/v1/auth/rbac/super-admin", headers=headers)
    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json()["role"] == role.value


@pytest.mark.parametrize("role,expected_status", [
    (UserRole.SUPER_ADMIN, 200),
    (UserRole.ORGANIZATION_ADMIN, 200),
    (UserRole.SITE_MANAGER, 200),
    (UserRole.STATION_OPERATOR, 403),
    (UserRole.TECHNICIAN, 403),
    (UserRole.VIEWER, 403),
    (UserRole.OWNER, 403),
    (UserRole.FAMILY_MEMBER, 403)
])
def test_admin_or_manager_endpoint(client: TestClient, role: UserRole, expected_status: int):
    headers = get_auth_headers(client, role)
    response = client.get("/api/v1/auth/rbac/admin-or-manager", headers=headers)
    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json()["role"] == role.value


def test_anonymous_user(client: TestClient):
    response = client.get("/api/v1/auth/rbac/super-admin")
    assert response.status_code == 401

def test_invalid_token(client: TestClient):
    response = client.get("/api/v1/auth/rbac/super-admin", headers={"Authorization": "Bearer invalid_token"})
    assert response.status_code == 401
