"""
HydraControl — Station Domain Model
Represents a logical/physical pump station or operational area inside a Site.
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
    from app.models.site import Site
    from app.models.controller import Controller
    from app.models.automation_rule import AutomationRule
    from app.models.settings import StationSettings
    from app.models.audit_log import AuditLog


class StationStatus(str, enum.Enum):
    """Operational status of a station."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    MAINTENANCE = "MAINTENANCE"


class StationType(str, enum.Enum):
    """Categorization of station types."""
    HOME_PUMP = "HOME_PUMP"
    WATER_SUPPLY = "WATER_SUPPLY"
    BOREWELL = "BOREWELL"
    IRRIGATION = "IRRIGATION"
    INDUSTRIAL = "INDUSTRIAL"
    RO_PLANT = "RO_PLANT"
    TREATMENT = "TREATMENT"
    DISTRIBUTION = "DISTRIBUTION"
    OTHER = "OTHER"


class Station(BaseModel):
    """
    Station entity representing a logical/physical pump station inside a Site.
    Hierarchy:
    Organization -> Site -> Station -> Controller (linked in P1-T07)
    """
    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("site_id", "station_code", name="uq_stations_site_code"),
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sites.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    station_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    station_type: Mapped[StationType] = mapped_column(
        Enum(StationType, native_enum=False, length=50),
        nullable=False
    )
    location: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Kolkata",
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    status: Mapped[StationStatus] = mapped_column(
        Enum(StationStatus, native_enum=False, length=50),
        default=StationStatus.ACTIVE,
        nullable=False,
        index=True
    )

    # Relationships
    site: Mapped["Site"] = relationship(
        "Site",
        back_populates="stations",
        lazy="selectin"
    )
    controllers: Mapped[list["Controller"]] = relationship(
        "Controller",
        back_populates="station",
        lazy="selectin"
    )
    automation_rules: Mapped[list["AutomationRule"]] = relationship(
        "AutomationRule",
        back_populates="station",
        lazy="selectin"
    )
    settings: Mapped[Optional["StationSettings"]] = relationship(
        "StationSettings",
        back_populates="station",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="station",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Station {self.name} [{self.station_code}] ({self.status.value}) id={self.id}>"
