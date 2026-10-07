import pytest
from datetime import timedelta
from jose import jwt, JWTError

from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    ALGORITHM
)
from app.core.config import settings

def test_password_hashing():
    password = "supersecretpassword"
    hashed = get_password_hash(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_jwt_creation_and_decoding():
    subject = "user123"
    token = create_access_token(subject)
    
    # decode valid token
    payload = decode_access_token(token)
    assert payload["sub"] == subject
    assert "exp" in payload

def test_jwt_custom_expiration():
    subject = "user123"
    expires_delta = timedelta(minutes=5)
    token = create_access_token(subject, expires_delta=expires_delta)
    
    payload = decode_access_token(token)
    assert payload["sub"] == subject

def test_invalid_jwt():
    with pytest.raises(JWTError):
        decode_access_token("invalid.token.string")

def test_expired_jwt():
    # create a token that expires in the past
    expires_delta = timedelta(minutes=-1)
    token = create_access_token("user123", expires_delta=expires_delta)
    
    with pytest.raises(JWTError):
        decode_access_token(token)
