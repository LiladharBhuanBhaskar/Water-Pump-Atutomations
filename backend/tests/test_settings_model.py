import uuid
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.settings import StationSettings
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.organization import Organization
    from backend.app.models.site import Site, SiteType
    from backend.app.models.station import Station, StationType
    from backend.app.models.settings import StationSettings
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_settings_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_settings_model_inheritance_and_metadata():
    """Verify StationSettings inherits BaseModel and checks column definitions."""
    assert issubclass(StationSettings, BaseModel)
    assert "station_settings" in Base.metadata.tables
    table = Base.metadata.tables["station_settings"]
    assert "id" in table.columns
    assert "station_id" in table.columns
    assert "timezone" in table.columns
    assert "auto_stop_on_tank_full" in table.columns
    assert "water_level_threshold" in table.columns
    assert "turbidity_threshold" in table.columns
    assert "default_timer_seconds" in table.columns
    assert "offline_alert_enabled" in table.columns
    assert "offline_timeout_seconds" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns

    # Verify foreign key and uniqueness
    station_id_col = table.columns["station_id"]
    assert len(station_id_col.foreign_keys) == 1
    fk = list(station_id_col.foreign_keys)[0]
    assert fk.column.table.name == "stations"
    assert fk.ondelete == "CASCADE"
    assert station_id_col.unique is True
    assert station_id_col.index is True


def _create_station(session):
    unique_suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Set Org {unique_suffix}", organization_code=f"SET-ORG-{unique_suffix}")
    session.add(org)
    session.flush()

    site = Site(organization_id=org.id, name=f"Set Site {unique_suffix}", site_code=f"SET-SITE-{unique_suffix}", site_type=SiteType.OTHER)
    session.add(site)
    session.flush()

    stn = Station(site_id=site.id, name=f"Set Station {unique_suffix}", station_code=f"SET-STN-{unique_suffix}", station_type=StationType.OTHER)
    session.add(stn)
    session.flush()

    return org, site, stn


def test_settings_default_values_and_nullables():
    """Verify default values and optional nullables upon creation."""
    with get_sync_session() as session:
        org, site, stn = _create_station(session)

        settings = StationSettings(station_id=stn.id)
        session.add(settings)
        session.flush()

        # Core required properties
        assert settings.id is not None
        assert settings.station_id == stn.id
        
        # Defaults
        assert settings.timezone == "Asia/Kolkata"
        assert settings.auto_stop_on_tank_full is False
        assert settings.offline_alert_enabled is True
        assert settings.offline_timeout_seconds == 300
        
        # Nullables
        assert settings.water_level_threshold is None
        assert settings.turbidity_threshold is None
        assert settings.default_timer_seconds is None

        # Timestamps inherited
        assert settings.created_at is not None
        assert settings.updated_at is not None


def test_settings_storage_and_precision():
    """Verify decimal precision, integers, and timezone strings are stored correctly."""
    with get_sync_session() as session:
        org, site, stn = _create_station(session)

        settings = StationSettings(
            station_id=stn.id,
            timezone="America/New_York",
            auto_stop_on_tank_full=True,
            water_level_threshold=Decimal("85.123456"),
            turbidity_threshold=Decimal("5.000000"),
            default_timer_seconds=1800,
            offline_alert_enabled=False,
            offline_timeout_seconds=600
        )
        session.add(settings)
        session.flush()

        settings_id = settings.id

    with get_sync_session() as session:
        settings = session.get(StationSettings, settings_id)
        assert settings.timezone == "America/New_York"
        assert settings.auto_stop_on_tank_full is True
        assert settings.water_level_threshold == Decimal("85.123456")
        assert settings.turbidity_threshold == Decimal("5.000000")
        assert settings.default_timer_seconds == 1800
        assert settings.offline_alert_enabled is False
        assert settings.offline_timeout_seconds == 600


def test_settings_bidirectional_relationship():
    """Verify Station -> Settings and Settings -> Station."""
    with get_sync_session() as session:
        org, site, stn = _create_station(session)
        
        settings = StationSettings(station_id=stn.id)
        session.add(settings)
        session.flush()

        stn_id = stn.id
        settings_id = settings.id

    with get_sync_session() as session:
        stn = session.get(Station, stn_id)
        assert stn.settings is not None
        assert stn.settings.id == settings_id
        
        settings = session.get(StationSettings, settings_id)
        assert settings.station is not None
        assert settings.station.id == stn_id


def test_one_to_one_unique_constraint():
    """Verify a station cannot have two settings records."""
    with get_sync_session() as session:
        org, site, stn = _create_station(session)
        
        settings_1 = StationSettings(station_id=stn.id)
        session.add(settings_1)
        session.flush()
        stn_id = stn.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            settings_2 = StationSettings(station_id=stn_id)
            session.add(settings_2)
            session.flush()


def test_multiple_stations_have_settings():
    """Verify multiple stations can each have their own settings."""
    with get_sync_session() as session:
        org1, site1, stn1 = _create_station(session)
        org2, site2, stn2 = _create_station(session)
        
        settings_1 = StationSettings(station_id=stn1.id)
        settings_2 = StationSettings(station_id=stn2.id)
        
        session.add(settings_1)
        session.add(settings_2)
        session.flush()
        
        assert settings_1.id is not None
        assert settings_2.id is not None


def test_settings_requires_station():
    """Verify settings cannot be created without a station_id."""
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            settings = StationSettings(station_id=None)
            session.add(settings)
            session.flush()


def test_station_deletion_cascades_to_settings():
    """Verify deleting a station completely deletes its settings (CASCADE)."""
    with get_sync_session() as session:
        org, site, stn = _create_station(session)
        
        settings = StationSettings(station_id=stn.id)
        session.add(settings)
        session.flush()
        
        stn_id = stn.id
        settings_id = settings.id
        
    with get_sync_session() as session:
        stn_to_delete = session.get(Station, stn_id)
        session.delete(stn_to_delete)
        session.flush()
        
    with get_sync_session() as session:
        assert session.get(StationSettings, settings_id) is None


@pytest.mark.asyncio
async def test_settings_async_crud():
    """Verify basic async functionality."""
    async with get_async_session() as session:
        unique_suffix = uuid.uuid4().hex[:6]
        
        org = Organization(name=f"Async Org {unique_suffix}", organization_code=f"ASYNC-ORG-{unique_suffix}")
        session.add(org)
        await session.flush()
        
        site = Site(organization_id=org.id, name=f"Async Site {unique_suffix}", site_code=f"ASYNC-SITE-{unique_suffix}", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        
        stn = Station(site_id=site.id, name=f"Async Station {unique_suffix}", station_code=f"ASYNC-STN-{unique_suffix}", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()
        
        settings = StationSettings(station_id=stn.id)
        session.add(settings)
        await session.flush()
        settings_id = settings.id

    async with get_async_session() as session:
        result = await session.execute(select(StationSettings).where(StationSettings.id == settings_id))
        queried = result.scalar_one()
        
        queried.default_timer_seconds = 120
        await session.flush()
        
        assert queried.default_timer_seconds == 120
