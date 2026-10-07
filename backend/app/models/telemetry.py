"""
HydraControl — Telemetry Model
Represents a single telemetry reading from a sensor.
"""
import uuid
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Uuid, ForeignKey, DateTime, JSON, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.sensor import Sensor


class TelemetryReading(BaseModel):
    """
    Database record for a single measurement value reported by a sensor over time.
    Hierarchy: Sensor -> TelemetryReading
    """
    __tablename__ = "telemetry_readings"

    sensor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sensors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    value: Mapped[float] = mapped_column(
        Numeric(20, 6),
        nullable=False
    )
    unit: Mapped[str] = mapped_column(
        String(32),
        nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSON,
        nullable=True
    )

    # Relationships
    sensor: Mapped["Sensor"] = relationship(
        "Sensor",
        back_populates="telemetry_readings",
        lazy="selectin"
    )

    # Composite index for querying history
    __table_args__ = (
        Index("ix_telemetry_readings_sensor_id_occurred_at", "sensor_id", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<TelemetryReading {self.value} {self.unit} id={self.id}>"
