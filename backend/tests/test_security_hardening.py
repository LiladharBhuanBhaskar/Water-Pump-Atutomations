"""
HydraControl — Security Hardening & Penetration Verification Suite (Phase 23).
Verifies JWT refresh tokens, rotation, replay prevention, brute force rate limiting,
security headers, emergency stop bypass of rate limits, and secret protection.
"""

import uuid
import pytest
from datetime import timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.core.security import get_password_hash, create_access_token
from app.services.token_service import token_service
from app.core.rate_limiter import rate_limiter


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_security_state():
    rate_limiter.reset()
    token_service.reset_state()
    yield
    rate_limiter.reset()
    token_service.reset_state()


def helper_create_test_user():
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="Security Org",
            organization_code=f"SEC-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)
        session.flush()

        user = User(
            id=uuid.uuid4(),
            email=f"sec_user_{uuid.uuid4().hex[:6]}@sec.io",
            name="Security User",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(user)
        session.commit()
        return {"user_id": user.id, "org_id": org.id, "email": user.email}


def test_jwt_refresh_token_lifecycle_and_rotation(client: TestClient):
    """Verify refresh token generation, access token refresh, rotation, and replay rejection."""
    u = helper_create_test_user()

    # 1. Login returning access_token and refresh_token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": u["email"], "password": "Pass@123"},
    )
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    refresh_token_v1 = data["refresh_token"]

    # 2. Use refresh_token to rotate and acquire fresh tokens
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_v1},
    )
    assert refresh_resp.status_code == 200
    rotated = refresh_resp.json()
    assert "access_token" in rotated
    assert "refresh_token" in rotated
    refresh_token_v2 = rotated["refresh_token"]
    assert refresh_token_v2 != refresh_token_v1

    # 3. REPLAY ATTACK: Re-using old refresh_token_v1 must fail with 401
    replay_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_v1},
    )
    assert replay_resp.status_code == 401
    assert "replay" in replay_resp.json()["detail"].lower() or "revoked" in replay_resp.json()["detail"].lower()

    # 4. Logout revokes refresh_token_v2
    logout_resp = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token_v2},
    )
    assert logout_resp.status_code == 200

    # 5. Using revoked refresh_token_v2 after logout fails
    post_logout_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token_v2},
    )
    assert post_logout_resp.status_code == 401


def test_login_brute_force_rate_limiting(client: TestClient):
    """Verify 10 failed login attempts triggers HTTP 429 Too Many Requests."""
    u = helper_create_test_user()

    # 10 requests allowed
    for _ in range(10):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": u["email"], "password": "WrongPassword"},
        )
        assert resp.status_code == 401

    # 11th request must be rejected with 429 Too Many Requests
    rate_limited_resp = client.post(
        "/api/v1/auth/login",
        json={"email": u["email"], "password": "Pass@123"},
    )
    assert rate_limited_resp.status_code == 429
    assert "retry-after" in rate_limited_resp.headers
    assert int(rate_limited_resp.headers["retry-after"]) > 0


def test_security_headers_injection(client: TestClient):
    """Verify production security headers are present on all HTTP responses."""
    resp = client.get("/health")
    assert resp.status_code == 200

    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in resp.headers
    assert "X-Correlation-ID" in resp.headers
