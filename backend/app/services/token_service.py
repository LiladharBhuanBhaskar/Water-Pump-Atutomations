"""
HydraControl — Token & Session Security Service (Phase 23).
Manages secure JWT refresh token generation, rotation, revocation,
replay prevention, and user/organization identity binding without database migrations.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Set
from jose import jwt, JWTError
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import ALGORITHM, create_access_token


class RefreshTokenPayload(BaseModel):
    jti: str
    sub: str  # user_id
    org_id: Optional[str] = None
    role: Optional[str] = None
    exp: int


class TokenService:
    def __init__(self):
        # In-memory storage of active token identifiers (jti) mapped to user metadata
        # In production this can be backed by Redis or DB
        self._active_refresh_tokens: Dict[str, dict] = {}
        # Revoked / used token IDs to detect replay attacks
        self._revoked_tokens: Set[str] = set()
        self.refresh_token_expire_days = 7

    def create_refresh_token(
        self,
        user_id: uuid.UUID,
        organization_id: Optional[uuid.UUID] = None,
        role: Optional[str] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Generates a secure, rotatable refresh token with unique JTI."""
        jti = str(uuid.uuid4())
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)

        payload = {
            "jti": jti,
            "sub": str(user_id),
            "org_id": str(organization_id) if organization_id else None,
            "role": role,
            "type": "refresh",
            "exp": int(expire.timestamp()),
        }

        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

        # Track active JTI
        self._active_refresh_tokens[jti] = {
            "user_id": str(user_id),
            "org_id": str(organization_id) if organization_id else None,
            "role": role,
            "expires_at": expire,
        }

        return token

    def rotate_refresh_token(self, refresh_token: str) -> tuple[str, str, str]:
        """
        Validates the refresh token, revokes the old token (rotation),
        and issues a fresh (access_token, refresh_token) pair.
        Raises ValueError on expired, revoked, replayed, or invalid tokens.
        """
        try:
            payload_dict = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError as e:
            raise ValueError(f"Invalid or expired refresh token: {e}")

        if payload_dict.get("type") != "refresh":
            raise ValueError("Token provided is not a refresh token")

        jti = payload_dict.get("jti")
        user_id_str = payload_dict.get("sub")
        org_id_str = payload_dict.get("org_id")
        role = payload_dict.get("role")

        if not jti or not user_id_str:
            raise ValueError("Malformed refresh token payload")

        # Check for replay attack: token was already revoked / used
        if jti in self._revoked_tokens:
            raise ValueError("Security Alert: Replay attack detected. Token has already been rotated/revoked.")

        # Verify token is in active registry
        if jti not in self._active_refresh_tokens:
            raise ValueError("Refresh token is unrecognized or revoked")

        # Invalidate old JTI (Rotation & Revocation)
        del self._active_refresh_tokens[jti]
        self._revoked_tokens.add(jti)

        user_id = uuid.UUID(user_id_str)
        org_id = uuid.UUID(org_id_str) if org_id_str else None

        # Issue new Access Token & new Refresh Token
        new_access_token = create_access_token(
            subject=user_id,
            extra_claims={"org_id": org_id_str, "role": role} if org_id_str else {"role": role},
        )
        new_refresh_token = self.create_refresh_token(
            user_id=user_id,
            organization_id=org_id,
            role=role,
        )

        return new_access_token, new_refresh_token, user_id_str

    def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revokes a refresh token explicitly on logout."""
        try:
            payload_dict = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
            jti = payload_dict.get("jti")
            if jti:
                self._active_refresh_tokens.pop(jti, None)
                self._revoked_tokens.add(jti)
                return True
        except JWTError:
            pass
        return False

    def reset_state(self):
        """Cleans in-memory state for isolated test execution."""
        self._active_refresh_tokens.clear()
        self._revoked_tokens.clear()


token_service = TokenService()
