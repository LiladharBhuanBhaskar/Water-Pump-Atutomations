import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class TelemetryReadingResponse(BaseModel):
    id: uuid.UUID
    sensor_id: uuid.UUID
    value: float
    unit: str
    occurred_at: datetime
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TelemetryIngestItem(BaseModel):
    value: float
    unit: Optional[str] = None
    occurred_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class TelemetryBatchIngestRequest(BaseModel):
    readings: List[TelemetryIngestItem]
