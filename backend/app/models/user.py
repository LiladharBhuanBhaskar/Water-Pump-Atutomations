"""
HydraControl — User Domain Model
Represents platform users, administrators, technicians, and home owners with RBAC roles.
"""
import uuid
import enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.automation_rule import AutomationRule
    from app.models.audit_log import AuditLog


class UserRole(str, enum.Enum):
    """
    User roles supporting both Enterprise and Home multi-tenant modes.
    Inherits from str for seamless JSON serialization and clean SQL storage.
    """
    # Enterprise Roles
    SUPER_ADMIN = "SUPER_ADMIN"
    ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN"
    SITE_MANAGER = "SITE_MANAGER"
    STATION_OPERATOR = "STATION_OPERATOR"
    TECHNICIAN = "TECHNICIAN"
    VIEWER = "VIEWER"

    # Home / Property Roles
    OWNER = "OWNER"
    FAMILY_MEMBER = "FAMILY_MEMBER"


class User(BaseModel):
    """
    User entity for identity, access control, and auditing.
    Inherits UUID primary key and timezone-aware created_at/updated_at from BaseModel.
    """
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=50),
        default=UserRole.VIEWER,
        nullable=False,
        index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )
    # Organization Foreign Key (nullable for unassigned/system users)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization",
        back_populates="users",
        lazy="selectin"
    )
    motor_commands: Mapped[list["MotorCommand"]] = relationship(
        "MotorCommand",
        back_populates="requester",
        lazy="selectin"
    )
    created_automation_rules: Mapped[list["AutomationRule"]] = relationship(
        "AutomationRule",
        back_populates="creator",
        lazy="selectin"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="actor_user",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value}) id={self.id}>"
