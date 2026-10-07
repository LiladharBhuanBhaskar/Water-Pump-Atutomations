"""
HydraControl — Audit Log Model
Represents historical, append-only application/business/security audit actions.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String, Boolean, Integer, Numeric, Uuid, ForeignKey,
    DateTime, JSON, Enum as SQLEnum, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel, utc_now
except ImportError:
    from backend.app.models.base import BaseModel, utc_now

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.site import Site
    from app.models.station import Station
    from app.models.user import User


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    START = "START"
    STOP = "STOP"
    RESET = "RESET"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    CONFIGURE = "CONFIGURE"
    ENABLE = "ENABLE"
    DISABLE = "DISABLE"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"
    OTHER = "OTHER"


class AuditActorType(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    CONTROLLER = "CONTROLLER"
    AUTOMATION = "AUTOMATION"


class AuditLog(BaseModel):
    """
    Historical log of important application and business events.
    Append-only. Deletions of referenced entities use SET NULL to preserve history.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_resource_type_resource_id", "resource_type", "resource_id"),
        Index("ix_audit_logs_organization_id_occurred_at", "organization_id", "occurred_at"),
    )

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sites.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    station_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    
    actor_type: Mapped[AuditActorType] = mapped_column(
        SQLEnum(AuditActorType, native_enum=False),
        nullable=False,
        default=AuditActorType.USER
    )
    
    action: Mapped[AuditAction] = mapped_column(
        SQLEnum(AuditAction, native_enum=False),
        nullable=False
    )
    
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True
    )
    
    action_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    
    audit_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True
    )
    
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True
    )
    
    occurred_at: Mapped[str] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        back_populates="audit_logs",
        lazy="selectin"
    )
    
    site: Mapped[Optional["Site"]] = relationship(
        "Site",
        back_populates="audit_logs",
        lazy="selectin"
    )
    
    station: Mapped[Optional["Station"]] = relationship(
        "Station",
        back_populates="audit_logs",
        lazy="selectin"
    )
    
    actor_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AuditLog action={self.action.value} resource={self.resource_type} id={self.id}>"
