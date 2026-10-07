"""
HydraControl — Motor Command Model
Represents a database record of an intended motor operation.
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
    from app.models.user import User


class CommandType(str, enum.Enum):
    """Categorization of motor commands."""
    START = "START"
    STOP = "STOP"
    RESET = "RESET"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class CommandStatus(str, enum.Enum):
    """Lifecycle state of a motor command."""
    PENDING = "PENDING"
    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class MotorCommand(BaseModel):
    """
    Database record for an intended motor operation.
    Hierarchy: Motor -> MotorCommand
    """
    __tablename__ = "motor_commands"

    motor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("motors.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    command_type: Mapped[CommandType] = mapped_column(
        Enum(CommandType, native_enum=False, length=50),
        nullable=False
    )
    status: Mapped[CommandStatus] = mapped_column(
        Enum(CommandStatus, native_enum=False, length=50),
        default=CommandStatus.PENDING,
        nullable=False
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    command_payload: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    failed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True
    )

    # Relationships
    motor: Mapped["Motor"] = relationship(
        "Motor",
        back_populates="commands",
        lazy="selectin"
    )
    requester: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="motor_commands",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<MotorCommand {self.command_type.value} ({self.status.value}) id={self.id}>"
