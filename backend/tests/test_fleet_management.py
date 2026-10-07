"""
HydraControl — Unit & Integration Tests for Enterprise Fleet Management (Phase 20).
Verifies multi-site aggregation, live operational counters (running, off, fault, offline),
active safety alert rollups, total power kW, strict tenant isolation, and RBAC.
"""

import uuid
from decimal import Decimal
import pytest
from datetime import datetime, timezone
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
from app.models.sensor import Sensor, SensorType, SensorStatus
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


def helper_create_fleet_hierarchy():
    """Builds two distinct organizations with sites, stations, controllers, motors, and sensors."""
    with get_sync_session() as session:
        # Org 1: Alpha Agri
        org1 = Organization(
            id=uuid.uuid4(),
            name="Alpha Agri Enterprise",
            organization_code=f"AGRI-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org1)
        session.flush()

        # Admin for Org 1
        user1 = User(
            id=uuid.uuid4(),
            email=f"admin_alpha_{uuid.uuid4().hex[:6]}@test.io",
            name="Alpha Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org1.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(user1)

        # Site 1 in Org 1: North Valley
        site1 = Site(
            id=uuid.uuid4(),
            name="North Valley Orchards",
            site_code=f"SITE-{uuid.uuid4().hex[:4].upper()}",
            site_type=SiteType.AGRICULTURE,
            organization_id=org1.id,
            status=SiteStatus.ACTIVE,
        )
        session.add(site1)
        session.flush()

        # Site 2 in Org 1: South Basin
        site2 = Site(
            id=uuid.uuid4(),
            name="South Basin Wells",
            site_code=f"SITE-{uuid.uuid4().hex[:4].upper()}",
            site_type=SiteType.PUMP_STATION,
            organization_id=org1.id,
            status=SiteStatus.ACTIVE,
        )
        session.add(site2)
        session.flush()

        # Station 1 in Site 1
        st1 = Station(
            id=uuid.uuid4(),
            name="Pump House 1",
            station_code=f"ST-{uuid.uuid4().hex[:4].upper()}",
            station_type=StationType.IRRIGATION,
            site_id=site1.id,
            status=StationStatus.ACTIVE,
        )
        session.add(st1)
        session.flush()

        # Controller 1 in Station 1 (ACTIVE/ONLINE)
        c1 = Controller(
            id=uuid.uuid4(),
            name="ESP32-ST1-01",
            controller_code=f"CTRL-{uuid.uuid4().hex[:4].upper()}",
            device_uid=f"DEV-{uuid.uuid4().hex[:8].upper()}",
            controller_type=ControllerType.ESP32,
            station_id=st1.id,
            status=ControllerStatus.ACTIVE,
        )
        session.add(c1)
        session.flush()

        # Motor 1 on Controller 1: ON (Running), 7.5 kW
        m1 = Motor(
            id=uuid.uuid4(),
            name="Primary Submersible 10HP",
            motor_code=f"MTR-{uuid.uuid4().hex[:4].upper()}",
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            controller_id=c1.id,
            rated_power=Decimal("7.50"),
            status=MotorStatus.ON,
        )
        session.add(m1)

        # Motor 2 on Controller 1: FAULT, 5.5 kW
        m2 = Motor(
            id=uuid.uuid4(),
            name="Secondary Booster 7.5HP",
            motor_code=f"MTR-{uuid.uuid4().hex[:4].upper()}",
            motor_type=MotorType.BOOSTER_PUMP,
            controller_id=c1.id,
            rated_power=Decimal("5.50"),
            status=MotorStatus.FAULT,
        )
        session.add(m2)

        # Sensor on Controller 1: Turbidity Monitor
        s1 = Sensor(
            id=uuid.uuid4(),
            name="Turbidity Monitor A",
            sensor_code=f"SNS-{uuid.uuid4().hex[:4].upper()}",
            controller_id=c1.id,
            sensor_type=SensorType.TURBIDITY,
            status=SensorStatus.ACTIVE,
        )
        session.add(s1)

        # Station 2 in Site 2
        st2 = Station(
            id=uuid.uuid4(),
            name="Deep Well Station 2",
            station_code=f"ST-{uuid.uuid4().hex[:4].upper()}",
            station_type=StationType.BOREWELL,
            site_id=site2.id,
            status=StationStatus.ACTIVE,
        )
        session.add(st2)
        session.flush()

        # Controller 2 in Station 2 (OFFLINE)
        c2 = Controller(
            id=uuid.uuid4(),
            name="ESP32-ST2-01",
            controller_code=f"CTRL-{uuid.uuid4().hex[:4].upper()}",
            device_uid=f"DEV-{uuid.uuid4().hex[:8].upper()}",
            controller_type=ControllerType.ESP32,
            station_id=st2.id,
            status=ControllerStatus.OFFLINE,
        )
        session.add(c2)
        session.flush()

        # Motor 3 on Controller 2: OFF, 11.0 kW
        m3 = Motor(
            id=uuid.uuid4(),
            name="Main Line Pump 15HP",
            motor_code=f"MTR-{uuid.uuid4().hex[:4].upper()}",
            motor_type=MotorType.WATER_PUMP,
            controller_id=c2.id,
            rated_power=Decimal("11.00"),
            status=MotorStatus.OFF,
        )
        session.add(m3)

        # Org 2: Beta Commercial (Isolated Tenant)
        org2 = Organization(
            id=uuid.uuid4(),
            name="Beta Utilities Corp",
            organization_code=f"BETA-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org2)
        session.flush()

        # Admin for Org 2
        user2 = User(
            id=uuid.uuid4(),
            email=f"admin_beta_{uuid.uuid4().hex[:6]}@test.io",
            name="Beta Org Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org2.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(user2)

        # Super Admin (Global scope)
        super_user = User(
            id=uuid.uuid4(),
            email=f"super_{uuid.uuid4().hex[:6]}@test.io",
            name="Global Platform Admin",
            role=UserRole.SUPER_ADMIN,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(super_user)

        session.commit()

        return {
            "org1_id": org1.id,
            "org1_name": org1.name,
            "user1_id": user1.id,
            "site1_id": site1.id,
            "site2_id": site2.id,
            "org2_id": org2.id,
            "user2_id": user2.id,
            "super_user_id": super_user.id,
        }


def test_fleet_summary_aggregation_and_calculations(client: TestClient):
    """Verify fleet summary returns accurate multi-site totals, operational status, and fault rollups."""
    data = helper_create_fleet_hierarchy()
    token1 = create_access_token(data["user1_id"])

    resp = client.get(
        f"/api/v1/organizations/{data['org1_id']}/fleet-summary",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    fleet = resp.json()

    # Organization overview
    assert fleet["organization_id"] == str(data["org1_id"])
    assert fleet["organization_name"] == data["org1_name"]
    assert fleet["site_count"] == 2
    assert fleet["station_count"] == 2
    assert fleet["controller_count"] == 2
    assert fleet["online_controllers"] == 1
    assert fleet["offline_controllers"] == 1

    # Motor Status Tally
    # Total motors = 3 (m1: ON, m2: FAULT, m3: OFF)
    motors = fleet["motors"]
    assert motors["total"] == 3
    assert motors["running"] == 1
    assert motors["fault"] == 1
    assert motors["off"] == 1
    assert motors["offline"] == 0

    # Power totals
    assert fleet["total_power_kw"] == 7.5  # only m1 (ON) consumes active power 7.5 kW

    # Active Safety Alerts Rollup
    alerts = fleet["active_safety_alerts"]
    assert len(alerts) == 1
    assert alerts[0]["status"] == "FAULT"

    # Sites list
    assert len(fleet["sites"]) == 2
    site_names = [s["site_name"] for s in fleet["sites"]]
    assert "North Valley Orchards" in site_names
    assert "South Basin Wells" in site_names


def test_fleet_summary_tenant_isolation_and_rbac(client: TestClient):
    """Verify strict tenant isolation and IDOR prevention on fleet summary."""
    data = helper_create_fleet_hierarchy()
    token_org1 = create_access_token(data["user1_id"])
    token_org2 = create_access_token(data["user2_id"])
    token_super = create_access_token(data["super_user_id"])

    # 1. Org 2 Admin queries Org 1 -> Forbidden (404 / IDOR prevention)
    cross_resp = client.get(
        f"/api/v1/organizations/{data['org1_id']}/fleet-summary",
        headers={"Authorization": f"Bearer {token_org2}"},
    )
    assert cross_resp.status_code == 404

    # 2. Org 1 Admin queries Org 2 -> Forbidden (404)
    cross_resp2 = client.get(
        f"/api/v1/organizations/{data['org2_id']}/fleet-summary",
        headers={"Authorization": f"Bearer {token_org1}"},
    )
    assert cross_resp2.status_code == 404

    # 3. Super Admin queries Org 1 -> Allowed (200)
    super_resp = client.get(
        f"/api/v1/organizations/{data['org1_id']}/fleet-summary",
        headers={"Authorization": f"Bearer {token_super}"},
    )
    assert super_resp.status_code == 200
    assert super_resp.json()["organization_id"] == str(data["org1_id"])

    # 4. Super Admin queries Org 2 (Empty fleet) -> Allowed (200 with 0s)
    super_resp2 = client.get(
        f"/api/v1/organizations/{data['org2_id']}/fleet-summary",
        headers={"Authorization": f"Bearer {token_super}"},
    )
    assert super_resp2.status_code == 200
    org2_fleet = super_resp2.json()
    assert org2_fleet["site_count"] == 0
    assert org2_fleet["motors"]["total"] == 0
    assert org2_fleet["total_power_kw"] == 0.0
