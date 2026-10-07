"""
HydraControl — Automation Rule Model
Represents an automation rule configuration for a station.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Enum, Uuid, ForeignKey, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.station import Station
    from app.models.sensor import Sensor
    from app.models.motor import Motor
    from app.models.user import User


class AutomationRuleType(str, enum.Enum):
    """Type of the automation rule."""
    WATER_LEVEL = "WATER_LEVEL"
    TURBIDITY = "TURBIDITY"
    TIMER = "TIMER"


class AutomationOperator(str, enum.Enum):
    """Comparison operator for telemetry-based conditions."""
    GREATER_THAN = "GREATER_THAN"
    GREATER_THAN_OR_EQUAL = "GREATER_THAN_OR_EQUAL"
    LESS_THAN = "LESS_THAN"
    LESS_THAN_OR_EQUAL = "LESS_THAN_OR_EQUAL"
    EQUAL = "EQUAL"


class AutomationAction(str, enum.Enum):
    """Action to execute when the rule condition is met."""
    START_MOTOR = "START_MOTOR"
    STOP_MOTOR = "STOP_MOTOR"
    RESET_MOTOR = "RESET_MOTOR"
    EMERGENCY_STOP_MOTOR = "EMERGENCY_STOP_MOTOR"


class AutomationRuleStatus(str, enum.Enum):
    """Current status of the automation rule."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AutomationRule(BaseModel):
    """
    Database record for an automation rule configuration.
    Belongs to a Station, optionally uses a Sensor for condition, targets a Motor.
    """
    __tablename__ = "automation_rules"

    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    rule_type: Mapped[AutomationRuleType] = mapped_column(
        Enum(AutomationRuleType, native_enum=False, length=50),
        nullable=False
    )
    status: Mapped[AutomationRuleStatus] = mapped_column(
        Enum(AutomationRuleStatus, native_enum=False, length=50),
        nullable=False,
        default=AutomationRuleStatus.ACTIVE
    )
    sensor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sensors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    operator: Mapped[Optional[AutomationOperator]] = mapped_column(
        Enum(AutomationOperator, native_enum=False, length=50),
        nullable=True
    )
    threshold_value: Mapped[Optional[float]] = mapped_column(
        Numeric(20, 6),
        nullable=True
    )
    threshold_unit: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    motor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("motors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    action: Mapped[AutomationAction] = mapped_column(
        Enum(AutomationAction, native_enum=False, length=50),
        nullable=False
    )
    cooldown_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Relationships
    station: Mapped["Station"] = relationship(
        "Station",
        back_populates="automation_rules",
        lazy="selectin"
    )
    sensor: Mapped[Optional["Sensor"]] = relationship(
        "Sensor",
        back_populates="automation_rules",
        lazy="selectin"
    )
    motor: Mapped["Motor"] = relationship(
        "Motor",
        back_populates="automation_rules",
        lazy="selectin"
    )
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_automation_rules",
        lazy="selectin"
    )

    # Composite index
    __table_args__ = (
        Index("ix_automation_rules_station_status", "station_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<AutomationRule {self.name} ({self.rule_type.value}) id={self.id}>"
