from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt
import bcrypt
from app.core.config import settings

ALGORITHM = "HS256"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None, extra_claims: dict = None
) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    if extra_claims:
        to_encode.update(extra_claims)
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_device_token(
    device_uid: str,
    controller_id: Union[str, Any],
    extra_claims: dict = None,
    expires_delta: timedelta = None
) -> str:
    claims = {
        "type": "device",
        "controller_id": str(controller_id),
    }
    if extra_claims:
        claims.update(extra_claims)
    if expires_delta is None:
        expires_delta = timedelta(days=365)
    return create_access_token(subject=device_uid, expires_delta=expires_delta, extra_claims=claims)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
