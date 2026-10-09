"""
HydraControl — User & Subscription Schemas
Provides type-safe models for Admin User Management and Business Subscriptions.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
import uuid
from typing import Optional, List
from datetime import datetime
from app.models.user import UserRole


class UserAdminCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = UserRole.STATION_OPERATOR
    organization_id: Optional[uuid.UUID] = None


class UserAdminUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    organization_id: Optional[uuid.UUID] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionPlanInfo(BaseModel):
    tier: str
    name: str
    price_monthly: float
    price_annual: float
    max_motors: int
    max_stations: int
    max_users: int
    features: List[str]


class SubscriptionResponse(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_code: str
    tier: str
    status: str
    max_motors: int
    current_motors: int
    max_stations: int
    current_stations: int
    max_users: int
    current_users: int
    billing_cycle: str
    renewal_date: str
    features: List[str]


class SubscriptionUpdateRequest(BaseModel):
    tier: str
    billing_cycle: Optional[str] = "ANNUAL"
