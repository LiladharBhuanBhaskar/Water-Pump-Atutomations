import uuid
import pytest
import asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationStatus, StationType
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.organization import Organization
    from backend.app.models.site import Site, SiteType
    from backend.app.models.station import Station, StationStatus, StationType
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_station_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_station_model_inheritance_and_metadata():
    """Verify Station model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(Station, BaseModel)
    assert "stations" in Base.metadata.tables
    table = Base.metadata.tables["stations"]
    assert "id" in table.columns
    assert "site_id" in table.columns
    assert "name" in table.columns
    assert "station_code" in table.columns
    assert "station_type" in table.columns
    assert "location" in table.columns
    assert "timezone" in table.columns
    assert "description" in table.columns
    assert "status" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_station_creation_and_defaults_sync():
    """Verify station creation with defaults (timezone='Asia/Kolkata', status='ACTIVE')."""
    with get_sync_session() as session:
        org = Organization(
            name="Apex Water Solutions",
            organization_code="APEX-STN-ORG"
        )
        session.add(org)
        session.flush()

        site = Site(
            organization_id=org.id,
            name="Jaipur Residence",
            site_code="STN-SITE-001",
            site_type=SiteType.HOME
        )
        session.add(site)
        session.flush()

        station = Station(
            site_id=site.id,
            name="Main Home Pump",
            station_code="HOME-PUMP-01",
            station_type=StationType.HOME_PUMP,
            location="Ground Floor",
            description="Main underground water pumping station."
        )
        session.add(station)
        session.flush()

        assert station.id is not None
        assert isinstance(station.id, uuid.UUID)
        assert station.site_id == site.id
        assert station.name == "Main Home Pump"
        assert station.station_code == "HOME-PUMP-01"
        assert station.station_type == StationType.HOME_PUMP
        assert station.timezone == "Asia/Kolkata"
        assert station.status == StationStatus.ACTIVE
        assert station.location == "Ground Floor"
        assert station.description == "Main underground water pumping station."
        assert isinstance(station.created_at, datetime)
        assert isinstance(station.updated_at, datetime)
        station_id = station.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(Station, station_id)
        assert queried is not None
        assert queried.id == station_id
        assert queried.station_code == "HOME-PUMP-01"
        assert "HOME-PUMP-01" in str(queried)


def test_multi_site_scoped_station_code_uniqueness():
    """
    Verify multi-tenant uniqueness:
    Site A + STN-001 = valid
    Site B + STN-001 = valid
    Site A + STN-001 again = raises IntegrityError
    """
    with get_sync_session() as session:
        org = Organization(name="Org Multiple Sites", organization_code="ORG-MULT-SITES")
        session.add(org)
        session.flush()

        site_a = Site(organization_id=org.id, name="Site Alpha", site_code="SITE-A", site_type=SiteType.FACTORY)
        site_b = Site(organization_id=org.id, name="Site Beta", site_code="SITE-B", site_type=SiteType.FACTORY)
        session.add_all([site_a, site_b])
        session.flush()

        # Both sites can have a station with the same station_code
        stn_a1 = Station(
            site_id=site_a.id,
            name="Alpha Station",
            station_code="STN-001",
            station_type=StationType.INDUSTRIAL
        )
        stn_b1 = Station(
            site_id=site_b.id,
            name="Beta Station",
            station_code="STN-001",
            station_type=StationType.INDUSTRIAL
        )
        session.add_all([stn_a1, stn_b1])
        session.flush()

        assert stn_a1.id is not None
        assert stn_b1.id is not None
        site_a_id = site_a.id

    # Inserting duplicate station_code in Site Alpha must fail
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            duplicate_stn = Station(
                site_id=site_a_id,
                name="Alpha Duplicate",
                station_code="STN-001",
                station_type=StationType.OTHER
            )
            session.add(duplicate_stn)
            session.flush()


def test_station_types_coverage():
    """Verify all defined StationType enum values are supported."""
    station_types = [
        StationType.HOME_PUMP,
        StationType.WATER_SUPPLY,
        StationType.BOREWELL,
        StationType.IRRIGATION,
        StationType.INDUSTRIAL,
        StationType.RO_PLANT,
        StationType.TREATMENT,
        StationType.DISTRIBUTION,
        StationType.OTHER,
    ]

    with get_sync_session() as session:
        org = Organization(name="Station Type Utility", organization_code="ORG-STN-TYPES")
        session.add(org)
        session.flush()
        
        site = Site(organization_id=org.id, name="Site Types", site_code="SITE-TYPES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        for idx, s_type in enumerate(station_types):
            s = Station(
                site_id=site.id,
                name=f"Station {s_type.value}",
                station_code=f"TYPE-{idx:03d}",
                station_type=s_type
            )
            session.add(s)
        session.flush()
        site_id = site.id

    # Verify query back
    with get_sync_session() as session:
        stations = session.execute(
            select(Station).where(Station.site_id == site_id)
        ).scalars().all()
        assert len(stations) == len(station_types)
        persisted_types = {s.station_type for s in stations}
        assert persisted_types == set(station_types)


def test_station_status_states():
    """Verify all StationStatus enum values (ACTIVE, INACTIVE, SUSPENDED, MAINTENANCE)."""
    statuses = [
        (StationStatus.ACTIVE, "STAT-001"),
        (StationStatus.INACTIVE, "STAT-002"),
        (StationStatus.SUSPENDED, "STAT-003"),
        (StationStatus.MAINTENANCE, "STAT-004"),
    ]

    with get_sync_session() as session:
        org = Organization(name="Station Status Org", organization_code="ORG-STN-STATUS")
        session.add(org)
        session.flush()
        
        site = Site(organization_id=org.id, name="Site Status", site_code="SITE-STATUS", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        for status, code in statuses:
            s = Station(
                site_id=site.id,
                name=f"Station {status.value}",
                station_code=code,
                station_type=StationType.OTHER,
                status=status
            )
            session.add(s)
        session.flush()

    with get_sync_session() as session:
        for status, code in statuses:
            s = session.execute(
                select(Station).where(Station.station_code == code)
            ).scalar_one()
            assert s.status == status


def test_site_station_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Site.stations and Station.site."""
    with get_sync_session() as session:
        org = Organization(
            name="Delhi Water Authority",
            organization_code="DEL-WATER-AUTH"
        )
        session.add(org)
        session.flush()

        site = Site(
            organization=org,
            name="Delhi Plant #1",
            site_code="DEL-PLT-01",
            site_type=SiteType.WATER_PLANT
        )
        session.add(site)
        session.flush()
        
        stn1 = Station(
            site=site,
            name="Main Pump Station",
            station_code="STN-01",
            station_type=StationType.PUMP_STATION if hasattr(StationType, "PUMP_STATION") else StationType.WATER_SUPPLY
        )
        stn2 = Station(
            site=site,
            name="Secondary Pump Station",
            station_code="STN-02",
            station_type=StationType.PUMP_STATION if hasattr(StationType, "PUMP_STATION") else StationType.WATER_SUPPLY
        )
        session.add_all([stn1, stn2])
        session.flush()

        site_id = site.id
        stn1_id = stn1.id

    # Verify Site -> Stations
    with get_sync_session() as session:
        fetched_site = session.get(Site, site_id)
        assert fetched_site is not None
        assert len(fetched_site.stations) == 2
        stn_codes = [s.station_code for s in fetched_site.stations]
        assert "STN-01" in stn_codes
        assert "STN-02" in stn_codes

    # Verify Station -> Site
    with get_sync_session() as session:
        fetched_stn = session.get(Station, stn1_id)
        assert fetched_stn is not None
        assert fetched_stn.site is not None
        assert fetched_stn.site.site_code == "DEL-PLT-01"


@pytest.mark.asyncio
async def test_station_async_crud_and_updated_at():
    """Verify async session operations and updated_at changes."""
    async with get_async_session() as session:
        org = Organization(name="Async Org For Station", organization_code="ASYNC-STN-ORG")
        session.add(org)
        await session.flush()
        
        site = Site(organization_id=org.id, name="Async Site", site_code="ASYNC-SITE", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()

        stn = Station(
            site_id=site.id,
            name="Async Station Initial",
            station_code="ASYNC-STN-01",
            station_type=StationType.OTHER,
            timezone="Asia/Kolkata"
        )
        session.add(stn)
        await session.flush()
        stn_id = stn.id
        initial_updated_at = stn.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(Station).where(Station.id == stn_id))
        stn_to_update = result.scalar_one()
        stn_to_update.name = "Async Station Renamed"
        stn_to_update.status = StationStatus.MAINTENANCE
        await session.flush()

        assert stn_to_update.name == "Async Station Renamed"
        assert stn_to_update.status == StationStatus.MAINTENANCE
        assert stn_to_update.updated_at >= initial_updated_at


def test_station_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        org = Organization(name="Fail Org", organization_code="FAIL-ORG-STN")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Fail Site", site_code="FAIL-SITE", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        site_id = site.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing name
            s = Station(site_id=site_id, station_code="S1", station_type=StationType.OTHER)
            session.add(s)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing station_code
            s = Station(site_id=site_id, name="S1", station_type=StationType.OTHER)
            session.add(s)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing site_id
            s = Station(name="S1", station_code="S1", station_type=StationType.OTHER)
            session.add(s)
            session.flush()
