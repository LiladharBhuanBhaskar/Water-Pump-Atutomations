"""
HydraControl — Organization Domain Model
Represents the root tenant entity (company, plant owner, or commercial client) in the multi-tenant hierarchy.
"""
import enum
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.site import Site
    from app.models.audit_log import AuditLog


class OrganizationStatus(str, enum.Enum):
    """Lifecycle status for organizations/tenants."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class Organization(BaseModel):
    """
    Organization entity forming the top-level boundary for multi-tenancy.
    Hierarchy:
    Organization -> Users
    Organization -> Sites
    """
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )
    organization_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False
    )
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, native_enum=False, length=50),
        default=OrganizationStatus.ACTIVE,
        nullable=False,
        index=True
    )

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        back_populates="organization",
        lazy="selectin"
    )
    sites: Mapped[List["Site"]] = relationship(
        "Site",
        back_populates="organization",
        lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="organization",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Organization {self.name} [{self.organization_code}] ({self.status.value}) id={self.id}>"
