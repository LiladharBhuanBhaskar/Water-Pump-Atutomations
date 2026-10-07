"""
HydraControl — Station Settings Model
Represents operational configuration for a physical station.
"""
import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, Numeric, Uuid, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from app.models.base import BaseModel
except ImportError:
    from backend.app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.station import Station


class StationSettings(BaseModel):
    """
    Database record for station-level operational settings.
    Belongs to exactly one Station (One-to-One relationship).
    """
    __tablename__ = "station_settings"

    station_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True
    )
    
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Asia/Kolkata"
    )
    
    auto_stop_on_tank_full: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )
    
    water_level_threshold: Mapped[Optional[float]] = mapped_column(
        Numeric(20, 6),
        nullable=True
    )
    
    turbidity_threshold: Mapped[Optional[float]] = mapped_column(
        Numeric(20, 6),
        nullable=True
    )
    
    default_timer_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    
    offline_alert_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )
    
    offline_timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=300
    )

    # Relationships
    station: Mapped["Station"] = relationship(
        "Station",
        back_populates="settings",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<StationSettings station_id={self.station_id} id={self.id}>"
