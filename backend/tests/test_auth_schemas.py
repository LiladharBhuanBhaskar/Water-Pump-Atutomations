import pytest
from pydantic import ValidationError

from app.schemas.auth import UserRegistrationRequest, LoginRequest, TokenResponse

def test_user_registration_request_valid():
    req = UserRegistrationRequest(
        name="Test User",
        email="test@example.com",
        password="securepassword123"
    )
    assert req.name == "Test User"
    assert req.email == "test@example.com"
    assert req.password == "securepassword123"

def test_user_registration_request_invalid_email():
    with pytest.raises(ValidationError):
        UserRegistrationRequest(
            name="Test User",
            email="not-an-email",
            password="securepassword123"
        )

def test_user_registration_request_missing_fields():
    with pytest.raises(ValidationError):
        UserRegistrationRequest(
            name="Test User"
        )

def test_user_registration_request_invalid_password():
    with pytest.raises(ValidationError):
        UserRegistrationRequest(
            name="Test User",
            email="test@example.com",
            password="short"  # less than 8 characters
        )

def test_login_request_valid():
    req = LoginRequest(
        email="test@example.com",
        password="securepassword123"
    )
    assert req.email == "test@example.com"
    assert req.password == "securepassword123"

def test_login_request_invalid_email():
    with pytest.raises(ValidationError):
        LoginRequest(
            email="not-an-email",
            password="securepassword123"
        )

def test_token_response_valid():
    resp = TokenResponse(
        access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    )
    assert resp.access_token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    assert resp.token_type == "bearer"
