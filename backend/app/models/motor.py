"""
HydraControl — Motor Domain Model
Represents a physical water pump/motor assigned to a Controller.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import String, Enum, Uuid, ForeignKey, UniqueConstraint, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.controller import Controller
    from app.models.motor_command import MotorCommand
    from app.models.motor_event import MotorEvent
    from app.models.automation_rule import AutomationRule


class MotorType(str, enum.Enum):
    """Categorization of motor/pump hardware types."""
    WATER_PUMP = "WATER_PUMP"
    SUBMERSIBLE_PUMP = "SUBMERSIBLE_PUMP"
    BOREWELL_PUMP = "BOREWELL_PUMP"
    BOOSTER_PUMP = "BOOSTER_PUMP"
    IRRIGATION_PUMP = "IRRIGATION_PUMP"
    CENTRIFUGAL_PUMP = "CENTRIFUGAL_PUMP"
    INDUSTRIAL_PUMP = "INDUSTRIAL_PUMP"
    OTHER = "OTHER"


class MotorStatus(str, enum.Enum):
    """Database lifecycle and runtime state of a motor."""
    OFFLINE = "OFFLINE"
    OFF = "OFF"
    ON = "ON"
    STARTING = "STARTING"
    STOPPING = "STOPPING"
    FAULT = "FAULT"
    MAINTENANCE = "MAINTENANCE"
    DISABLED = "DISABLED"


class Motor(BaseModel):
    """
    Motor entity representing a physical pump linked to a Controller.
    Hierarchy:
    Organization -> Site -> Station -> Controller -> Motor
    """
    __tablename__ = "motors"
    __table_args__ = (
        UniqueConstraint("controller_id", "motor_code", name="uq_motors_controller_code"),
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
    motor_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )
    motor_type: Mapped[MotorType] = mapped_column(
        Enum(MotorType, native_enum=False, length=50),
        default=MotorType.WATER_PUMP,
        nullable=False
    )
    status: Mapped[MotorStatus] = mapped_column(
        Enum(MotorStatus, native_enum=False, length=50),
        default=MotorStatus.OFFLINE,
        nullable=False
    )
    rated_power: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Relationships
    controller: Mapped["Controller"] = relationship(
        "Controller",
        back_populates="motors",
        lazy="selectin"
    )
    commands: Mapped[list["MotorCommand"]] = relationship(
        "MotorCommand",
        back_populates="motor",
        lazy="selectin"
    )
    events: Mapped[list["MotorEvent"]] = relationship(
        "MotorEvent",
        back_populates="motor",
        lazy="selectin"
    )
    automation_rules: Mapped[list["AutomationRule"]] = relationship(
        "AutomationRule",
        back_populates="motor",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Motor {self.name} [{self.motor_code}] ({self.status.value}) id={self.id}>"
