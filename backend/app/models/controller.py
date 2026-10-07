"""
HydraControl — Controller Domain Model
Represents a physical IoT/PLC/control device assigned to a Station.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import String, Enum, Uuid, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.station import Station
    from app.models.motor import Motor
    from app.models.sensor import Sensor


class ControllerStatus(str, enum.Enum):
    """Operational status of a controller."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"
    DECOMMISSIONED = "DECOMMISSIONED"


class ControllerType(str, enum.Enum):
    """Categorization of controller hardware types."""
    ESP32 = "ESP32"
    ESP32_ETHERNET = "ESP32_ETHERNET"
    ESP32_4G = "ESP32_4G"
    PLC = "PLC"
    INDUSTRIAL_GATEWAY = "INDUSTRIAL_GATEWAY"
    OTHER = "OTHER"


class Controller(BaseModel):
    """
    Controller entity representing a physical IoT device installed at a Station.
    Hierarchy:
    Organization -> Site -> Station -> Controller -> Motor (linked in P1-T08)
    """
    __tablename__ = "controllers"
    __table_args__ = (
        UniqueConstraint("station_id", "controller_code", name="uq_controllers_station_code"),
    )

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
    controller_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    device_uid: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True
    )
    controller_type: Mapped[ControllerType] = mapped_column(
        Enum(ControllerType, native_enum=False, length=50),
        nullable=False
    )
    status: Mapped[ControllerStatus] = mapped_column(
        Enum(ControllerStatus, native_enum=False, length=50),
        default=ControllerStatus.ACTIVE,
        nullable=False
    )
    firmware_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    mac_address: Mapped[Optional[str]] = mapped_column(
        String(17),
        nullable=True
    )
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )

    # Relationships
    station: Mapped["Station"] = relationship(
        "Station",
        back_populates="controllers",
        lazy="selectin"
    )
    motors: Mapped[list["Motor"]] = relationship(
        "Motor",
        back_populates="controller",
        lazy="selectin"
    )
    sensors: Mapped[list["Sensor"]] = relationship(
        "Sensor",
        back_populates="controller",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Controller {self.name} [{self.controller_code}] ({self.device_uid}) ({self.status.value}) id={self.id}>"
