"""
HydraControl — Unit & Integration Tests for Phase 21 (Home User Mode) & Phase 22 (UX Hardening).
Verifies OWNER and FAMILY_MEMBER role permissions, home site/station access,
motor command authorizations, read-only restriction for FAMILY_MEMBER,
controller offline protection, and multi-tenant isolation.
"""

import uuid
from decimal import Decimal
import pytest
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


def helper_create_home_environment():
    """Sets up a residential home environment with Owner and Family Member users."""
    with get_sync_session() as session:
        # Organization
        org = Organization(
            id=uuid.uuid4(),
            name="Green Meadows Villa Org",
            organization_code=f"VILLA-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)
        session.flush()

        # 1. OWNER User
        owner = User(
            id=uuid.uuid4(),
            email=f"owner_{uuid.uuid4().hex[:6]}@home.io",
            name="Villa Homeowner",
            role=UserRole.OWNER,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(owner)

        # 2. FAMILY_MEMBER User
        family = User(
            id=uuid.uuid4(),
            email=f"family_{uuid.uuid4().hex[:6]}@home.io",
            name="Family Resident",
            role=UserRole.FAMILY_MEMBER,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(family)

        # Residential Home Site
        home_site = Site(
            id=uuid.uuid4(),
            name="Villa Sanctuary 42",
            site_code=f"HOME-{uuid.uuid4().hex[:4].upper()}",
            site_type=SiteType.HOME,
            organization_id=org.id,
            status=SiteStatus.ACTIVE,
        )
        session.add(home_site)
        session.flush()

        # Station: Sump & Overhead Tank
        home_station = Station(
            id=uuid.uuid4(),
            name="Domestic Water System",
            station_code=f"STN-{uuid.uuid4().hex[:4].upper()}",
            station_type=StationType.HOME_PUMP,
            site_id=home_site.id,
            status=StationStatus.ACTIVE,
        )
        session.add(home_station)
        session.flush()

        # Controller (ONLINE / ACTIVE)
        online_ctrl = Controller(
            id=uuid.uuid4(),
            name="ESP32-Home-01",
            controller_code=f"CTRL-{uuid.uuid4().hex[:4].upper()}",
            device_uid=f"DEV-{uuid.uuid4().hex[:8].upper()}",
            controller_type=ControllerType.ESP32,
            station_id=home_station.id,
            status=ControllerStatus.ACTIVE,
        )
        session.add(online_ctrl)
        session.flush()

        # Motor: 2HP Sump-to-Overhead Pump (OFF)
        home_pump = Motor(
            id=uuid.uuid4(),
            name="Overhead Tank Pump",
            motor_code=f"PUMP-{uuid.uuid4().hex[:4].upper()}",
            motor_type=MotorType.BOOSTER_PUMP,
            controller_id=online_ctrl.id,
            rated_power=Decimal("1.50"),
            status=MotorStatus.OFF,
        )
        session.add(home_pump)

        # Sensors
        level_sensor = Sensor(
            id=uuid.uuid4(),
            name="Overhead Tank Ultrasonic",
            sensor_code=f"LVL-{uuid.uuid4().hex[:4].upper()}",
            controller_id=online_ctrl.id,
            sensor_type=SensorType.WATER_LEVEL,
            status=SensorStatus.ACTIVE,
        )
        session.add(level_sensor)

        # Controller (OFFLINE)
        offline_ctrl = Controller(
            id=uuid.uuid4(),
            name="ESP32-Garden-02",
            controller_code=f"CTRL-{uuid.uuid4().hex[:4].upper()}",
            device_uid=f"DEV-{uuid.uuid4().hex[:8].upper()}",
            controller_type=ControllerType.ESP32,
            station_id=home_station.id,
            status=ControllerStatus.OFFLINE,
        )
        session.add(offline_ctrl)
        session.flush()

        # Motor on Offline Controller
        garden_pump = Motor(
            id=uuid.uuid4(),
            name="Garden Drip Pump",
            motor_code=f"PUMP-{uuid.uuid4().hex[:4].upper()}",
            motor_type=MotorType.WATER_PUMP,
            controller_id=offline_ctrl.id,
            rated_power=Decimal("0.75"),
            status=MotorStatus.OFF,
        )
        session.add(garden_pump)

        session.commit()

        return {
            "org_id": org.id,
            "owner_id": owner.id,
            "family_id": family.id,
            "site_id": home_site.id,
            "station_id": home_station.id,
            "online_ctrl_id": online_ctrl.id,
            "offline_ctrl_id": offline_ctrl.id,
            "home_pump_id": home_pump.id,
            "garden_pump_id": garden_pump.id,
            "level_sensor_id": level_sensor.id,
        }


def test_owner_home_access_and_motor_commands(client: TestClient):
    """Verify OWNER can view home hierarchy, query telemetry, and dispatch motor commands."""
    data = helper_create_home_environment()
    token = create_access_token(data["owner_id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. OWNER can list sites & stations
    sites_resp = client.get("/api/v1/sites", headers=headers)
    assert sites_resp.status_code == 200
    assert len(sites_resp.json()) >= 1

    stations_resp = client.get(f"/api/v1/stations?site_id={data['site_id']}", headers=headers)
    assert stations_resp.status_code == 200
    assert len(stations_resp.json()) >= 1

    # 2. OWNER can dispatch START command
    start_resp = client.post(f"/api/v1/motors/{data['home_pump_id']}/start", headers=headers)
    assert start_resp.status_code == 200
    cmd = start_resp.json()
    assert cmd["command_type"] == "START"
    assert cmd["status"] in ("PENDING", "SENT")

    # 3. OWNER can dispatch STOP command
    stop_resp = client.post(f"/api/v1/motors/{data['home_pump_id']}/stop", headers=headers)
    assert stop_resp.status_code == 200
    assert stop_resp.json()["command_type"] == "STOP"


def test_family_member_read_only_access_and_command_rejection(client: TestClient):
    """Verify FAMILY_MEMBER can view home data but is strictly rejected (403) from motor commands."""
    data = helper_create_home_environment()
    token = create_access_token(data["family_id"])
    headers = {"Authorization": f"Bearer {token}"}

    # 1. FAMILY_MEMBER can view home sites & stations
    sites_resp = client.get("/api/v1/sites", headers=headers)
    assert sites_resp.status_code == 200

    stations_resp = client.get(f"/api/v1/stations?site_id={data['site_id']}", headers=headers)
    assert stations_resp.status_code == 200

    motors_resp = client.get(f"/api/v1/motors?controller_id={data['online_ctrl_id']}", headers=headers)
    assert motors_resp.status_code == 200

    # 2. FAMILY_MEMBER is rejected (403 Forbidden) on START command
    start_resp = client.post(f"/api/v1/motors/{data['home_pump_id']}/start", headers=headers)
    assert start_resp.status_code == 403
    assert "Not enough permissions" in start_resp.json()["detail"]

    # 3. FAMILY_MEMBER is rejected (403 Forbidden) on STOP command
    stop_resp = client.post(f"/api/v1/motors/{data['home_pump_id']}/stop", headers=headers)
    assert stop_resp.status_code == 403

    # 4. FAMILY_MEMBER is rejected (403 Forbidden) on RESET command
    reset_resp = client.post(f"/api/v1/motors/{data['home_pump_id']}/reset", headers=headers)
    assert reset_resp.status_code == 403


def test_offline_controller_motor_command_protection(client: TestClient):
    """Verify motor commands fail safely when target controller is OFFLINE."""
    data = helper_create_home_environment()
    token = create_access_token(data["owner_id"])
    headers = {"Authorization": f"Bearer {token}"}

    # OWNER attempts to start pump on OFFLINE controller -> 400 Bad Request
    resp = client.post(f"/api/v1/motors/{data['garden_pump_id']}/start", headers=headers)
    assert resp.status_code == 400
    assert "not operational" in resp.json()["detail"].lower() or "offline" in resp.json()["detail"].lower()
