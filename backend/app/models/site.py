"""
HydraControl — Site Domain Model
Represents physical customer locations, properties, plants, or pump stations scoped to an Organization.
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
    from app.models.organization import Organization
    from app.models.station import Station
    from app.models.audit_log import AuditLog


class SiteStatus(str, enum.Enum):
    """Operational status of a physical site."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    MAINTENANCE = "MAINTENANCE"


class SiteType(str, enum.Enum):
    """Categorization of physical location / customer installation."""
    HOME = "HOME"
    BUILDING = "BUILDING"
    FACTORY = "FACTORY"
    OFFICE = "OFFICE"
    AGRICULTURE = "AGRICULTURE"
    PUMP_STATION = "PUMP_STATION"
    WATER_PLANT = "WATER_PLANT"
    WAREHOUSE = "WAREHOUSE"
    OTHER = "OTHER"


class Site(BaseModel):
    """
    Site entity representing a physical property or facility within a tenant Organization.
    Hierarchy:
    Organization -> Site -> Station (linked in P1-T06)
    """
    __tablename__ = "sites"
    __table_args__ = (
        UniqueConstraint("organization_id", "site_code", name="uq_sites_org_code"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    site_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    site_type: Mapped[SiteType] = mapped_column(
        Enum(SiteType, native_enum=False, length=50),
        default=SiteType.HOME,
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
    status: Mapped[SiteStatus] = mapped_column(
        Enum(SiteStatus, native_enum=False, length=50),
        default=SiteStatus.ACTIVE,
        nullable=False,
        index=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="sites",
        lazy="selectin"
    )
    stations: Mapped[list["Station"]] = relationship(
        "Station",
        back_populates="site",
        lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="site",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Site {self.name} [{self.site_code}] ({self.status.value}) id={self.id}>"
