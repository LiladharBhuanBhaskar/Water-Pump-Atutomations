"""
HydraControl — Motor Event Model
Represents a historical database record of an event that occurred on a motor.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Enum, Uuid, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.motor import Motor


class MotorEventType(str, enum.Enum):
    """Categorization of motor events."""
    STARTED = "STARTED"
    STOPPED = "STOPPED"
    FAULT = "FAULT"
    RESET = "RESET"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"


class MotorEventSource(str, enum.Enum):
    """Source that caused the motor event."""
    USER = "USER"
    CONTROLLER = "CONTROLLER"
    SYSTEM = "SYSTEM"
    SENSOR = "SENSOR"
    AUTOMATION = "AUTOMATION"


class MotorEvent(BaseModel):
    """
    Database record for an event that actually occurred on a motor.
    Hierarchy: Motor -> MotorEvent
    """
    __tablename__ = "motor_events"

    motor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("motors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    event_type: Mapped[MotorEventType] = mapped_column(
        Enum(MotorEventType, native_enum=False, length=50),
        nullable=False
    )
    source: Mapped[MotorEventSource] = mapped_column(
        Enum(MotorEventSource, native_enum=False, length=50),
        nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    event_payload: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Relationships
    motor: Mapped["Motor"] = relationship(
        "Motor",
        back_populates="events",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<MotorEvent {self.event_type.value} ({self.source.value}) id={self.id}>"
