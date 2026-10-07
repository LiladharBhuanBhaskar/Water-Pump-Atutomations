import pytest
import uuid
from datetime import timedelta
from fastapi.testclient import TestClient
from sqlalchemy.future import select

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, get_async_session
from app.models.user import User, UserRole
from app.core.security import create_access_token, get_password_hash, verify_password

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for auth tests and drop them upon completion."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient instance."""
    with TestClient(app) as c:
        yield c

# ============================================================================
# 1. REGISTRATION TESTS
# ============================================================================

def test_register_valid_contract(client: TestClient):
    """Verify registration creates user and returns expected schema without leaking secrets."""
    payload = {
        "name": "Auth Standard User",
        "email": "standard.auth@example.com",
        "password": "securepassword123"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Auth Standard User"
    assert data["email"] == "standard.auth@example.com"
    assert data["is_active"] is True
    assert data["role"] == "VIEWER"
    assert "id" in data
    
    # Assert secrets are not leaked
    assert "password" not in data
    assert "password_hash" not in data
    assert "hashed_password" not in data

def test_register_email_case_insensitivity_and_uniqueness(client: TestClient):
    """Verify email normalization (lowercase) and duplicate registration rejection."""
    payload1 = {
        "name": "Case Test User 1",
        "email": "CaseInsensitive@Example.COM",
        "password": "password123"
    }
    res1 = client.post("/api/v1/auth/register", json=payload1)
    assert res1.status_code == 201
    assert res1.json()["email"] == "caseinsensitive@example.com"

    # Attempt registration with different casing for same email
    payload2 = {
        "name": "Case Test User 2",
        "email": "CASEINSENSITIVE@example.com",
        "password": "password456"
    }
    res2 = client.post("/api/v1/auth/register", json=payload2)
    assert res2.status_code == 409
    assert res2.json()["detail"] == "A user with this email already exists."

def test_register_password_hashing_in_database(client: TestClient):
    """Verify password is stored as bcrypt hash in DB and not as plaintext."""
    raw_password = "MyComplexPassword99!"
    payload = {
        "name": "Hash Verification User",
        "email": "hashcheck@example.com",
        "password": raw_password
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201
    user_id = uuid.UUID(res.json()["id"])

    with get_sync_session() as session:
        db_user = session.execute(select(User).where(User.id == user_id)).scalar_one()
        assert db_user.password_hash != raw_password
        assert db_user.password_hash.startswith("$2b$") or db_user.password_hash.startswith("$2a$")
        assert verify_password(raw_password, db_user.password_hash) is True

def test_register_invalid_email_format(client: TestClient):
    """Verify 422 Unprocessable Entity for malformed email addresses."""
    invalid_emails = ["plainaddress", "@missinguser.com", "user@.com", "user@domain", ""]
    for email in invalid_emails:
        payload = {"name": "Invalid Email User", "email": email, "password": "password123"}
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422

def test_register_missing_required_fields(client: TestClient):
    """Verify 422 Unprocessable Entity when required registration fields are missing."""
    incomplete_payloads = [
        {"email": "missingname@example.com", "password": "password123"},
        {"name": "Missing Email User", "password": "password123"},
        {"name": "Missing Password User", "email": "missingpass@example.com"},
        {}
    ]
    for payload in incomplete_payloads:
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422

# ============================================================================
# 2. LOGIN TESTS
# ============================================================================

def test_login_success_contract(client: TestClient):
    """Verify successful login returns valid JWT token and token_type."""
    reg_payload = {
        "name": "Login Contract User",
        "email": "logincontract@example.com",
        "password": "Password123!"
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "logincontract@example.com",
        "password": "Password123!"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200

    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert len(data["access_token"]) > 20

def test_login_case_insensitive_email(client: TestClient):
    """Verify login works regardless of email case."""
    reg_payload = {
        "name": "Case Login User",
        "email": "caselogin@example.com",
        "password": "Password123!"
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "CASELOGIN@EXAMPLE.COM",
        "password": "Password123!"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_login_incorrect_password(client: TestClient):
    """Verify 401 Unauthorized for incorrect password."""
    reg_payload = {
        "name": "Wrong Pass User",
        "email": "wrongpass@example.com",
        "password": "CorrectPassword123"
    }
    client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {
        "email": "wrongpass@example.com",
        "password": "WrongPassword123"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"
    assert res.headers.get("www-authenticate") == "Bearer"

def test_login_unknown_email(client: TestClient):
    """Verify 401 Unauthorized for non-existent email."""
    login_payload = {
        "email": "nonexistent.user@example.com",
        "password": "SomePassword123"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"
    assert res.headers.get("www-authenticate") == "Bearer"

def test_login_inactive_user(client: TestClient):
    """Verify 403 Forbidden for inactive user login attempt."""
    reg_payload = {
        "name": "Inactive Login User",
        "email": "inactivelogin@example.com",
        "password": "Password123!"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    user_id = uuid.UUID(reg_res.json()["id"])

    # Deactivate user in database
    with get_sync_session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one()
        user.is_active = False
        session.commit()

    login_payload = {
        "email": "inactivelogin@example.com",
        "password": "Password123!"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 403
    assert res.json()["detail"] == "User is inactive"

def test_login_malformed_request(client: TestClient):
    """Verify 422 Unprocessable Entity for invalid login request format."""
    res = client.post("/api/v1/auth/login", json={"email": "onlyemail@example.com"})
    assert res.status_code == 422

# ============================================================================
# 3. JWT TOKEN VALIDATION TESTS
# ============================================================================

def test_jwt_valid_token_access(client: TestClient):
    """Verify valid JWT token grants access to protected endpoints."""
    reg_payload = {
        "name": "JWT Access User",
        "email": "jwtaccess@example.com",
        "password": "Password123!"
    }
    client.post("/api/v1/auth/register", json=reg_payload)
    login_res = client.post("/api/v1/auth/login", json={"email": "jwtaccess@example.com", "password": "Password123!"})
    token = login_res.json()["access_token"]

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == "jwtaccess@example.com"

def test_jwt_expired_token_rejection(client: TestClient):
    """Verify expired JWT token returns 401 Unauthorized."""
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            name="Expired Token User",
            email="expiredjwt@example.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.VIEWER,
            is_active=True
        )
        session.add(user)
        session.commit()

    expired_token = create_access_token(subject=str(user_id), expires_delta=timedelta(minutes=-10))
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Could not validate credentials"
    assert res.headers.get("www-authenticate") == "Bearer"

def test_jwt_invalid_signature_rejection(client: TestClient):
    """Verify token signed with wrong secret key returns 401 Unauthorized."""
    from jose import jwt
    invalid_token = jwt.encode({"sub": str(uuid.uuid4())}, "wrong-secret-key-12345", algorithm="HS256")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {invalid_token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Could not validate credentials"

def test_jwt_malformed_string_rejection(client: TestClient):
    """Verify malformed token strings return 401 Unauthorized."""
    malformed_tokens = ["not.a.jwt", "12345", "BearerHeaderInvalid", "e30.e30.e30"]
    for token in malformed_tokens:
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401

def test_jwt_non_uuid_subject_rejection(client: TestClient):
    """Verify JWT payload with non-UUID sub claim returns 401 Unauthorized without 500 error."""
    from jose import jwt
    from app.core.config import settings
    token_bad_sub = jwt.encode({"sub": "invalid-non-uuid-string"}, settings.SECRET_KEY, algorithm="HS256")

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_bad_sub}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Could not validate credentials"

def test_jwt_nonexistent_user_sub_rejection(client: TestClient):
    """Verify JWT payload with non-existent user UUID returns 401 Unauthorized."""
    random_user_id = uuid.uuid4()
    token = create_access_token(subject=str(random_user_id))

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Could not validate credentials"

def test_jwt_missing_auth_header(client: TestClient):
    """Verify request without Authorization header returns 401 Unauthorized."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

# ============================================================================
# 4. CURRENT USER & AUTHORIZATION LIFECYCLE TESTS
# ============================================================================

def test_current_user_deactivation_revokes_active_token(client: TestClient):
    """Verify that deactivating a user invalidates pre-existing valid JWT tokens (HTTP 403)."""
    reg_payload = {
        "name": "Revocation User",
        "email": "revocation@example.com",
        "password": "Password123!"
    }
    reg_res = client.post("/api/v1/auth/register", json=reg_payload)
    user_id = uuid.UUID(reg_res.json()["id"])

    login_res = client.post("/api/v1/auth/login", json={"email": "revocation@example.com", "password": "Password123!"})
    valid_token = login_res.json()["access_token"]

    # Access /me while active -> 200 OK
    res_before = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
    assert res_before.status_code == 200

    # Deactivate user in DB
    with get_sync_session() as session:
        user = session.execute(select(User).where(User.id == user_id)).scalar_one()
        user.is_active = False
        session.commit()

    # Access /me with same token after deactivation -> 403 Forbidden
    res_after = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
    assert res_after.status_code == 403
    assert res_after.json()["detail"] == "Inactive user"

def test_rbac_endpoint_protection_chain(client: TestClient):
    """Verify the full authentication and RBAC dependency chain."""
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            name="Viewer User",
            email="rbacviewer@example.com",
            password_hash=get_password_hash("pass"),
            role=UserRole.VIEWER,
            is_active=True
        )
        session.add(user)
        session.commit()

    token = create_access_token(subject=str(user_id))

    # Access super-admin route as VIEWER -> 403 Forbidden
    res = client.get("/api/v1/auth/rbac/super-admin", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert res.json()["detail"] == "Not enough permissions"
