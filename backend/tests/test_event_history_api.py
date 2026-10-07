"""
HydraControl — Unit & Integration Tests for Event History API (Phase 18 - Wave A).
Verifies Motor and Station event history queries, date/type filtering, pagination, and multi-tenant isolation.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.core.security import create_access_token, get_password_hash


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def helper_setup_event_history():
    """Sets up an organization with users and historical motor events."""
    with get_sync_session() as session:
        org1 = Organization(
            id=uuid.uuid4(),
            name="Event History Org 1",
            organization_code=f"EV1-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        org2 = Organization(
            id=uuid.uuid4(),
            name="Event History Org 2",
            organization_code=f"EV2-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add_all([org1, org2])
        session.flush()

        super_admin = User(
            id=uuid.uuid4(),
            email=f"sadmin_{uuid.uuid4().hex[:6]}@events.io",
            name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        org1_admin = User(
            id=uuid.uuid4(),
            email=f"org1admin_{uuid.uuid4().hex[:6]}@events.io",
            name="Org1 Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org1.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        org2_admin = User(
            id=uuid.uuid4(),
            email=f"org2admin_{uuid.uuid4().hex[:6]}@events.io",
            name="Org2 Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org2.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add_all([super_admin, org1_admin, org2_admin])
        session.flush()

        site1 = Site(
            id=uuid.uuid4(),
            organization_id=org1.id,
            name="Event Site 1",
            site_code=f"SITE1-{uuid.uuid4().hex[:6].upper()}",
            site_type=SiteType.PUMP_STATION,
            status=SiteStatus.ACTIVE,
        )
        session.add(site1)
        session.flush()

        station1 = Station(
            id=uuid.uuid4(),
            site_id=site1.id,
            name="Event Station 1",
            station_code=f"STN1-{uuid.uuid4().hex[:6].upper()}",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE,
        )
        session.add(station1)
        session.flush()

        controller1 = Controller(
            id=uuid.uuid4(),
            station_id=station1.id,
            name="Event Controller 1",
            controller_code=f"CTRL1-{uuid.uuid4().hex[:6].upper()}",
            device_uid=f"DEV1-{uuid.uuid4().hex[:8].upper()}",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
        )
        session.add(controller1)
        session.flush()

        motor1 = Motor(
            id=uuid.uuid4(),
            controller_id=controller1.id,
            name="Event Motor 1",
            motor_code=f"PUMP1-{uuid.uuid4().hex[:6].upper()}",
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            status=MotorStatus.ON,
        )
        motor2 = Motor(
            id=uuid.uuid4(),
            controller_id=controller1.id,
            name="Event Motor 2",
            motor_code=f"PUMP2-{uuid.uuid4().hex[:6].upper()}",
            motor_type=MotorType.BOOSTER_PUMP,
            status=MotorStatus.OFF,
        )
        session.add_all([motor1, motor2])
        session.flush()

        base_time = datetime(2026, 10, 7, 8, 0, 0, tzinfo=timezone.utc)
        events = [
            MotorEvent(
                id=uuid.uuid4(),
                motor_id=motor1.id,
                event_type=MotorEventType.STARTED,
                source=MotorEventSource.USER,
                occurred_at=base_time,
                description="Motor started by operator",
            ),
            MotorEvent(
                id=uuid.uuid4(),
                motor_id=motor1.id,
                event_type=MotorEventType.STOPPED,
                source=MotorEventSource.AUTOMATION,
                occurred_at=base_time + timedelta(hours=1),
                description="Motor auto-stopped by tank full",
            ),
            MotorEvent(
                id=uuid.uuid4(),
                motor_id=motor1.id,
                event_type=MotorEventType.FAULT,
                source=MotorEventSource.CONTROLLER,
                occurred_at=base_time + timedelta(hours=2),
                description="Dry-run safety trip",
            ),
            MotorEvent(
                id=uuid.uuid4(),
                motor_id=motor1.id,
                event_type=MotorEventType.RESET,
                source=MotorEventSource.USER,
                occurred_at=base_time + timedelta(hours=3),
                description="Operator cleared fault",
            ),
            MotorEvent(
                id=uuid.uuid4(),
                motor_id=motor2.id,
                event_type=MotorEventType.EMERGENCY_STOP,
                source=MotorEventSource.USER,
                occurred_at=base_time + timedelta(hours=4),
                description="Emergency stop button pressed",
            ),
        ]
        session.add_all(events)
        session.commit()

        return {
            "org1": org1,
            "org2": org2,
            "super_admin": super_admin,
            "org1_admin": org1_admin,
            "org2_admin": org2_admin,
            "station1": station1,
            "motor1": motor1,
            "motor2": motor2,
            "base_time": base_time,
        }


def test_get_motor_events_api(client: TestClient):
    """Test retrieving events for a specific motor with type filtering and pagination."""
    fix = helper_setup_event_history()
    motor1 = fix["motor1"]
    super_admin_token = create_access_token(fix["super_admin"].id)

    # 1. Fetch all events for motor 1
    resp = client.get(
        f"/api/v1/motors/{motor1.id}/events",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    # Check descending order (latest event first)
    assert data[0]["event_type"] == "RESET"
    assert data[3]["event_type"] == "STARTED"

    # 2. Filter by event_type=FAULT
    fault_resp = client.get(
        f"/api/v1/motors/{motor1.id}/events?event_type=FAULT",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert fault_resp.status_code == 200
    fault_data = fault_resp.json()
    assert len(fault_data) == 1
    assert fault_data[0]["event_type"] == "FAULT"
    assert "Dry-run" in fault_data[0]["description"]

    # 3. Pagination limit=2, offset=1
    page_resp = client.get(
        f"/api/v1/motors/{motor1.id}/events?limit=2&offset=1",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert page_resp.status_code == 200
    page_data = page_resp.json()
    assert len(page_data) == 2


def test_get_station_events_api(client: TestClient):
    """Test station-wide event aggregation across all child motors."""
    fix = helper_setup_event_history()
    station1 = fix["station1"]
    super_admin_token = create_access_token(fix["super_admin"].id)

    # Fetch station-wide events (both motor 1 and motor 2)
    resp = client.get(
        f"/api/v1/stations/{station1.id}/events",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 5
    assert data[0]["event_type"] == "EMERGENCY_STOP"  # Latest event across entire station


def test_event_history_date_filtering_and_validation(client: TestClient):
    """Test date range filtering and validation."""
    fix = helper_setup_event_history()
    motor1 = fix["motor1"]
    base_time = fix["base_time"]
    super_admin_token = create_access_token(fix["super_admin"].id)

    # Valid date range covering first 2 events
    start_str = (base_time - timedelta(minutes=10)).isoformat()
    end_str = (base_time + timedelta(minutes=70)).isoformat()

    resp = client.get(
        f"/api/v1/motors/{motor1.id}/events",
        params={"start_time": start_str, "end_time": end_str},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Invalid date range: start_time > end_time returns 400
    invalid_resp = client.get(
        f"/api/v1/motors/{motor1.id}/events",
        params={"start_time": end_str, "end_time": start_str},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert invalid_resp.status_code == 400


def test_event_history_tenant_isolation(client: TestClient):
    """Verify cross-tenant motor event queries return 404 (IDOR prevention)."""
    fix = helper_setup_event_history()
    motor1 = fix["motor1"]
    station1 = fix["station1"]
    org2_admin_token = create_access_token(fix["org2_admin"].id)

    # Org2 Admin tries to access Org1's motor events -> 404
    resp = client.get(
        f"/api/v1/motors/{motor1.id}/events",
        headers={"Authorization": f"Bearer {org2_admin_token}"},
    )
    assert resp.status_code == 404

    # Org2 Admin tries to access Org1's station events -> 404
    resp_stn = client.get(
        f"/api/v1/stations/{station1.id}/events",
        headers={"Authorization": f"Bearer {org2_admin_token}"},
    )
    assert resp_stn.status_code == 404
