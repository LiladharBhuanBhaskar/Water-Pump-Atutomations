import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.models.station import StationStatus, StationType

class StationCreate(BaseModel):
    site_id: uuid.UUID = Field(..., description="Target physical Site ID")
    name: str = Field(..., min_length=1, max_length=150, description="Station display name")
    station_code: str = Field(..., min_length=1, max_length=50, description="Station code unique within site")
    station_type: Optional[StationType] = Field(default=StationType.HOME_PUMP, description="Categorization of station")
    location: Optional[str] = Field(default=None, max_length=255, description="Physical location address or details")
    timezone: Optional[str] = Field(default="Asia/Kolkata", max_length=64, description="Local station timezone")
    description: Optional[str] = Field(default=None, max_length=500, description="Detailed description")
    status: Optional[StationStatus] = Field(default=StationStatus.ACTIVE, description="Operational status")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v_stripped = v.strip()
        if not v_stripped:
            raise ValueError("Station name cannot be blank.")
        return v_stripped

    @field_validator("station_code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        v_cleaned = v.strip().upper()
        if not v_cleaned:
            raise ValueError("Station code cannot be blank.")
        return v_cleaned

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> str:
        if v is None or not v.strip():
            return "Asia/Kolkata"
        return v.strip()


class StationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    station_code: Optional[str] = Field(default=None, min_length=1, max_length=50)
    station_type: Optional[StationType] = None
    location: Optional[str] = Field(default=None, max_length=255)
    timezone: Optional[str] = Field(default=None, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)
    status: Optional[StationStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Station name cannot be blank.")
            return v_stripped
        return v

    @field_validator("station_code")
    @classmethod
    def validate_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v_cleaned = v.strip().upper()
            if not v_cleaned:
                raise ValueError("Station code cannot be blank.")
            return v_cleaned
        return v


class StationResponse(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    name: str
    station_code: str
    station_type: StationType
    location: Optional[str]
    timezone: str
    description: Optional[str]
    status: StationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
