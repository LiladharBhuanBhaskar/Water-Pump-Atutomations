"""
HydraControl — Models Base re-export
"""
try:
    from app.db.base import Base, BaseModel, UUIDMixin, TimestampMixin, utc_now
except ImportError:
    from backend.app.db.base import Base, BaseModel, UUIDMixin, TimestampMixin, utc_now

__all__ = ["Base", "BaseModel", "UUIDMixin", "TimestampMixin", "utc_now"]
