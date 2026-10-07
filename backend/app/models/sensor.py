"""
HydraControl — Sensor Domain Model
Represents a physical sensor device assigned to a Controller.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Enum, Uuid, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.controller import Controller
    from app.models.telemetry import TelemetryReading
    from app.models.automation_rule import AutomationRule


class SensorType(str, enum.Enum):
    """Categorization of sensor measurement types."""
    WATER_LEVEL = "WATER_LEVEL"
    TURBIDITY = "TURBIDITY"
    FLOW = "FLOW"
    PRESSURE = "PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    HUMIDITY = "HUMIDITY"
    CURRENT = "CURRENT"
    VOLTAGE = "VOLTAGE"
    PH = "PH"
    OTHER = "OTHER"


class SensorStatus(str, enum.Enum):
    """Database lifecycle state of a sensor."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    FAULT = "FAULT"
    MAINTENANCE = "MAINTENANCE"
    DISABLED = "DISABLED"


class Sensor(BaseModel):
    """
    Sensor entity representing a physical sensor linked to a Controller.
    Hierarchy:
    Organization -> Site -> Station -> Controller -> Sensor
    """
    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("controller_id", "sensor_code", name="uq_sensors_controller_code"),
    )

    controller_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("controllers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    sensor_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    sensor_type: Mapped[SensorType] = mapped_column(
        Enum(SensorType, native_enum=False, length=50),
        default=SensorType.OTHER,
        nullable=False
    )
    status: Mapped[SensorStatus] = mapped_column(
        Enum(SensorStatus, native_enum=False, length=50),
        default=SensorStatus.ACTIVE,
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Relationships
    controller: Mapped["Controller"] = relationship(
        "Controller",
        back_populates="sensors",
        lazy="selectin"
    )
    telemetry_readings: Mapped[list["TelemetryReading"]] = relationship(
        "TelemetryReading",
        back_populates="sensor",
        lazy="selectin"
    )
    automation_rules: Mapped[list["AutomationRule"]] = relationship(
        "AutomationRule",
        back_populates="sensor",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Sensor {self.name} [{self.sensor_code}] ({self.status.value}) id={self.id}>"
