import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.organization import OrganizationStatus

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150, description="Organization display name")
    organization_code: str = Field(..., min_length=1, max_length=50, description="Unique organization code")
    status: Optional[OrganizationStatus] = Field(default=OrganizationStatus.ACTIVE, description="Lifecycle status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Organization name cannot be blank.")
        return v_stripped

    @field_validator("organization_code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v_cleaned = v.strip().upper()
        if not v_cleaned:
            raise ValueError("Organization code cannot be blank.")
        return v_cleaned

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    organization_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    status: Optional[OrganizationStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Organization name cannot be blank.")
            return v_stripped
        return v

    @field_validator("organization_code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_cleaned = v.strip().upper()
            if not v_cleaned:
                raise ValueError("Organization code cannot be blank.")
            return v_cleaned
        return v

class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    organization_code: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
