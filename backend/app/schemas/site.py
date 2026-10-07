import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.site import SiteStatus, SiteType

class SiteCreate(BaseModel):
    organization_id: Optional[uuid.UUID] = Field(default=None, description="Target organization ID (for SUPER_ADMIN)")
    name: str = Field(..., min_length=1, max_length=150, description="Site display name")
    site_code: str = Field(..., min_length=1, max_length=50, description="Site code unique within organization")
    site_type: Optional[SiteType] = Field(default=SiteType.HOME, description="Category of location")
    location: Optional[str] = Field(default=None, max_length=255, description="Physical location address or details")
    timezone: Optional[str] = Field(default="Asia/Kolkata", max_length=64, description="Local site timezone")
    status: Optional[SiteStatus] = Field(default=SiteStatus.ACTIVE, description="Operational status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Site name cannot be blank.")
        return v_stripped

    @field_validator("site_code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v_cleaned = v.strip().upper()
        if not v_cleaned:
            raise ValueError("Site code cannot be blank.")
        return v_cleaned

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> str:
        if v is None or not v.strip():
            return "Asia/Kolkata"
        return v.strip()


class SiteUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    site_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    site_type: Optional[SiteType] = None
    location: Optional[str] = Field(default=None, max_length=255)
    timezone: Optional[str] = Field(default=None, max_length=64)
    status: Optional[SiteStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Site name cannot be blank.")
            return v_stripped
        return v

    @field_validator("site_code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_cleaned = v.strip().upper()
            if not v_cleaned:
                raise ValueError("Site code cannot be blank.")
            return v_cleaned
        return v


class SiteResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    site_code: str
    site_type: SiteType
    location: Optional[str]
    timezone: str
    status: SiteStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
