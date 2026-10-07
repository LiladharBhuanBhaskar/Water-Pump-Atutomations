from pydantic import BaseModel, EmailStr, Field, ConfigDict
import uuid
from typing import Optional

class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)


class UserRegistrationRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str
