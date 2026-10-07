import uuid
import pytest
import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.controller import Controller, ControllerStatus, ControllerType
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
    from backend.app.models.controller import Controller, ControllerStatus, ControllerType
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_controller_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_controller_model_inheritance_and_metadata():
    """Verify Controller model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(Controller, BaseModel)
    assert "controllers" in Base.metadata.tables
    table = Base.metadata.tables["controllers"]
    assert "id" in table.columns
    assert "station_id" in table.columns
    assert "name" in table.columns
    assert "controller_code" in table.columns
    assert "device_uid" in table.columns
    assert "controller_type" in table.columns
    assert "status" in table.columns
    assert "firmware_version" in table.columns
    assert "ip_address" in table.columns
    assert "mac_address" in table.columns
    assert "last_seen_at" in table.columns
    assert "description" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_controller_creation_and_defaults_sync():
    """Verify controller creation with defaults."""
    with get_sync_session() as session:
        org = Organization(name="Controller Org", organization_code="CTRL-ORG-01")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Controller Site", site_code="CTRL-SITE", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn = Station(site_id=site.id, name="Controller Station", station_code="CTRL-STN", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        now = datetime.now(timezone.utc)
        controller = Controller(
            station_id=stn.id,
            name="Main Controller",
            controller_code="CTRL-001",
            device_uid="ESP32-A1B2C3",
            controller_type=ControllerType.ESP32,
            firmware_version="1.0.0",
            ip_address="192.168.1.100",
            mac_address="AA:BB:CC:DD:EE:FF",
            last_seen_at=now,
            description="Main ESP32 controller"
        )
        session.add(controller)
        session.flush()

        assert controller.id is not None
        assert isinstance(controller.id, uuid.UUID)
        assert controller.station_id == stn.id
        assert controller.name == "Main Controller"
        assert controller.controller_code == "CTRL-001"
        assert controller.device_uid == "ESP32-A1B2C3"
        assert controller.controller_type == ControllerType.ESP32
        assert controller.status == ControllerStatus.ACTIVE
        assert controller.firmware_version == "1.0.0"
        assert controller.ip_address == "192.168.1.100"
        assert controller.mac_address == "AA:BB:CC:DD:EE:FF"
        assert controller.last_seen_at == now
        assert controller.description == "Main ESP32 controller"
        assert isinstance(controller.created_at, datetime)
        assert isinstance(controller.updated_at, datetime)
        controller_id = controller.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(Controller, controller_id)
        assert queried is not None
        assert queried.controller_code == "CTRL-001"
        assert "ESP32-A1B2C3" in str(queried)


def test_station_scoped_controller_code_uniqueness():
    """
    Verify multi-station uniqueness:
    Station A + CTRL-001 = valid
    Station B + CTRL-001 = valid
    Station A + CTRL-001 again = raises IntegrityError
    """
    with get_sync_session() as session:
        org = Organization(name="Org For Scoped Codes", organization_code="ORG-SCOPED-CODES")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Site For Codes", site_code="SITE-CODES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn_a = Station(site_id=site.id, name="Station Alpha", station_code="STN-ALPHA", station_type=StationType.OTHER)
        stn_b = Station(site_id=site.id, name="Station Beta", station_code="STN-BETA", station_type=StationType.OTHER)
        session.add_all([stn_a, stn_b])
        session.flush()

        c_a = Controller(
            station_id=stn_a.id,
            name="Controller A",
            controller_code="CTRL-100",
            device_uid="DEV-A-100",
            controller_type=ControllerType.OTHER
        )
        c_b = Controller(
            station_id=stn_b.id,
            name="Controller B",
            controller_code="CTRL-100",
            device_uid="DEV-B-100",
            controller_type=ControllerType.OTHER
        )
        session.add_all([c_a, c_b])
        session.flush()

        assert c_a.id is not None
        assert c_b.id is not None
        stn_a_id = stn_a.id

    # Inserting duplicate controller_code in Station A must fail
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            dup_c = Controller(
                station_id=stn_a_id,
                name="Duplicate Code",
                controller_code="CTRL-100",
                device_uid="DEV-DUP-100",
                controller_type=ControllerType.OTHER
            )
            session.add(dup_c)
            session.flush()


def test_device_uid_global_uniqueness():
    """Verify device_uid is globally unique, even across different stations."""
    with get_sync_session() as session:
        org = Organization(name="Org For UID", organization_code="ORG-UID-TEST")
        session.add(org)
        session.flush()

        site = Site(organization_id=org.id, name="Site UID", site_code="SITE-UID", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()

        stn1 = Station(site_id=site.id, name="Station 1 UID", station_code="STN-UID-1", station_type=StationType.OTHER)
        stn2 = Station(site_id=site.id, name="Station 2 UID", station_code="STN-UID-2", station_type=StationType.OTHER)
        session.add_all([stn1, stn2])
        session.flush()

        c1 = Controller(
            station_id=stn1.id,
            name="Controller 1",
            controller_code="C1",
            device_uid="GLOBAL-UID-01",
            controller_type=ControllerType.OTHER
        )
        session.add(c1)
        session.flush()
        stn2_id = stn2.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            c2 = Controller(
                station_id=stn2_id,
                name="Controller 2",
                controller_code="C2",
                device_uid="GLOBAL-UID-01",  # Duplicate UID
                controller_type=ControllerType.OTHER
            )
            session.add(c2)
            session.flush()


def test_controller_types_coverage():
    """Verify all defined ControllerType enum values are supported."""
    c_types = [
        ControllerType.ESP32,
        ControllerType.ESP32_ETHERNET,
        ControllerType.ESP32_4G,
        ControllerType.PLC,
        ControllerType.INDUSTRIAL_GATEWAY,
        ControllerType.OTHER,
    ]

    with get_sync_session() as session:
        org = Organization(name="Types Org", organization_code="ORG-CTYPES")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Types Site", site_code="SITE-CTYPES", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Types Station", station_code="STN-CTYPES", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        for idx, c_type in enumerate(c_types):
            c = Controller(
                station_id=stn.id,
                name=f"Controller {c_type.value}",
                controller_code=f"TYPE-{idx:03d}",
                device_uid=f"DEV-TYPE-{idx:03d}",
                controller_type=c_type
            )
            session.add(c)
        session.flush()
        stn_id = stn.id

    with get_sync_session() as session:
        controllers = session.execute(
            select(Controller).where(Controller.station_id == stn_id)
        ).scalars().all()
        assert len(controllers) == len(c_types)
        persisted_types = {c.controller_type for c in controllers}
        assert persisted_types == set(c_types)


def test_controller_status_states():
    """Verify all ControllerStatus enum values."""
    statuses = [
        (ControllerStatus.ACTIVE, "CS-001"),
        (ControllerStatus.INACTIVE, "CS-002"),
        (ControllerStatus.MAINTENANCE, "CS-003"),
        (ControllerStatus.OFFLINE, "CS-004"),
        (ControllerStatus.DECOMMISSIONED, "CS-005"),
    ]

    with get_sync_session() as session:
        org = Organization(name="Status Org", organization_code="ORG-CSTATUS")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Status Site", site_code="SITE-CSTATUS", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Status Station", station_code="STN-CSTATUS", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        for status, code in statuses:
            c = Controller(
                station_id=stn.id,
                name=f"Controller {status.value}",
                controller_code=code,
                device_uid=f"DEV-{code}",
                controller_type=ControllerType.OTHER,
                status=status
            )
            session.add(c)
        session.flush()

    with get_sync_session() as session:
        for status, code in statuses:
            c = session.execute(
                select(Controller).where(Controller.controller_code == code)
            ).scalar_one()
            assert c.status == status


def test_station_controller_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Station.controllers and Controller.station."""
    with get_sync_session() as session:
        org = Organization(name="Rel Org", organization_code="ORG-REL")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Rel Site", site_code="SITE-REL", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Rel Station", station_code="STN-REL", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()

        c1 = Controller(
            station=stn,
            name="Controller 1",
            controller_code="CR-01",
            device_uid="DEV-CR-01",
            controller_type=ControllerType.ESP32
        )
        c2 = Controller(
            station=stn,
            name="Controller 2",
            controller_code="CR-02",
            device_uid="DEV-CR-02",
            controller_type=ControllerType.PLC
        )
        session.add_all([c1, c2])
        session.flush()

        stn_id = stn.id
        c1_id = c1.id

    # Verify Station -> Controllers
    with get_sync_session() as session:
        fetched_stn = session.get(Station, stn_id)
        assert fetched_stn is not None
        assert len(fetched_stn.controllers) == 2
        c_codes = [c.controller_code for c in fetched_stn.controllers]
        assert "CR-01" in c_codes
        assert "CR-02" in c_codes

    # Verify Controller -> Station
    with get_sync_session() as session:
        fetched_c = session.get(Controller, c1_id)
        assert fetched_c is not None
        assert fetched_c.station is not None
        assert fetched_c.station.station_code == "STN-REL"


@pytest.mark.asyncio
async def test_controller_async_crud_and_updated_at():
    """Verify async session operations and updated_at changes."""
    async with get_async_session() as session:
        org = Organization(name="Async Org C", organization_code="ASYNC-ORG-C")
        session.add(org)
        await session.flush()
        site = Site(organization_id=org.id, name="Async Site C", site_code="ASYNC-SITE-C", site_type=SiteType.OTHER)
        session.add(site)
        await session.flush()
        stn = Station(site_id=site.id, name="Async Station C", station_code="ASYNC-STN-C", station_type=StationType.OTHER)
        session.add(stn)
        await session.flush()

        c = Controller(
            station_id=stn.id,
            name="Async Controller",
            controller_code="ASYNC-C-01",
            device_uid="DEV-ASYNC-01",
            controller_type=ControllerType.OTHER
        )
        session.add(c)
        await session.flush()
        c_id = c.id
        initial_updated_at = c.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(Controller).where(Controller.id == c_id))
        c_to_update = result.scalar_one()
        c_to_update.name = "Async Controller Renamed"
        c_to_update.status = ControllerStatus.MAINTENANCE
        await session.flush()

        assert c_to_update.name == "Async Controller Renamed"
        assert c_to_update.status == ControllerStatus.MAINTENANCE
        assert c_to_update.updated_at >= initial_updated_at


def test_controller_missing_fields_fail():
    """Verify missing required fields raise IntegrityError."""
    with get_sync_session() as session:
        org = Organization(name="Fail Org C", organization_code="FAIL-ORG-C")
        session.add(org)
        session.flush()
        site = Site(organization_id=org.id, name="Fail Site C", site_code="FAIL-SITE-C", site_type=SiteType.OTHER)
        session.add(site)
        session.flush()
        stn = Station(site_id=site.id, name="Fail Station C", station_code="FAIL-STN-C", station_type=StationType.OTHER)
        session.add(stn)
        session.flush()
        stn_id = stn.id

    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing name
            c = Controller(station_id=stn_id, controller_code="C1", device_uid="D1", controller_type=ControllerType.OTHER)
            session.add(c)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing controller_code
            c = Controller(station_id=stn_id, name="C1", device_uid="D1", controller_type=ControllerType.OTHER)
            session.add(c)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing device_uid
            c = Controller(station_id=stn_id, name="C1", controller_code="C1", controller_type=ControllerType.OTHER)
            session.add(c)
            session.flush()
            
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            # Missing station_id
            c = Controller(name="C1", controller_code="C1", device_uid="D1", controller_type=ControllerType.OTHER)
            session.add(c)
            session.flush()
