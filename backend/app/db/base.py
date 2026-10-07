"""
HydraControl — Database Declarative Base & Entity Mixins
Provides SQLAlchemy 2.x Declarative Base, cross-database UUID strategy, and timezone-aware timestamps.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """
    SQLAlchemy 2.x Declarative Base.
    AsyncAttrs enables async lazy loading and attribute evaluation.
    Exposes Base.metadata for Alembic migrations.
    """
    pass


class UUIDMixin:
    """
    UUID Primary Key Mixin.
    Uses SQLAlchemy 2.0 native Uuid type with Python uuid.UUID objects.
    Maps to native UUID in PostgreSQL and binary/char in SQLite.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False
    )


def utc_now() -> datetime:
    """Returns timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """
    Timezone-aware UTC timestamp tracking mixin.
    Stores full UTC timestamps for all creation and update events.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False
    )


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Abstract base entity that all HydraControl domain models inherit from.
    Provides automated UUID generation, UTC timestamps, and metadata integration.
    """
    __abstract__ = True
