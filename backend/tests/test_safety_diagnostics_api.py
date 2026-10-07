"""Tests for Water Quality, Flow Diagnostics, and Electrical Metrics APIs (Phase 12-15 - Wave 2B)."""

import uuid
from datetime import datetime, timezone
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
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.telemetry import TelemetryReading
from app.models.settings import StationSettings
from app.services.water_quality_service import WaterQualityStatus
from app.services.flow_protection_service import FlowSafetyStatus
from app.services.electrical_protection_service import ElectricalSafetyStatus
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


def helper_create_org(code: str, name: str) -> Organization:
    org_id = uuid.uuid4()
    with get_sync_session() as session:
        org = Organization(
            id=org_id,
            name=name,
            organization_code=code,
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)
        session.commit()
        session.refresh(org)
    return org


def helper_create_site(org_id: uuid.UUID, code: str, name: str) -> Site:
    site_id = uuid.uuid4()
    with get_sync_session() as session:
        site = Site(
            id=site_id,
            organization_id=org_id,
            name=name,
            site_code=code,
            site_type=SiteType.HOME,
            status=SiteStatus.ACTIVE
        )
        session.add(site)
        session.commit()
        session.refresh(site)
    return site


def helper_create_station(site_id: uuid.UUID, code: str, name: str) -> Station:
    station_id = uuid.uuid4()
    with get_sync_session() as session:
        station = Station(
            id=station_id,
            site_id=site_id,
            name=name,
            station_code=code,
            station_type=StationType.HOME_PUMP,
            status=StationStatus.ACTIVE,
            timezone="Asia/Kolkata"
        )
        session.add(station)
        session.commit()
        session.refresh(station)
    return station


def helper_create_controller(station_id: uuid.UUID, uid: str, code: str) -> Controller:
    controller_id = uuid.uuid4()
    with get_sync_session() as session:
        ctrl = Controller(
            id=controller_id,
            station_id=station_id,
            name="Diag Controller",
            controller_code=code,
            device_uid=uid,
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(ctrl)
        session.commit()
        session.refresh(ctrl)
    return ctrl


def helper_create_motor(controller_id: uuid.UUID, code: str, status: MotorStatus = MotorStatus.OFF) -> Motor:
    motor_id = uuid.uuid4()
    with get_sync_session() as session:
        m = Motor(
            id=motor_id,
            controller_id=controller_id,
            name="Diag Motor",
            motor_code=code,
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            status=status,
            rated_power=3.7
        )
        session.add(m)
        session.commit()
        session.refresh(m)
    return m


def helper_create_sensor(controller_id: uuid.UUID, code: str, stype: SensorType) -> Sensor:
    sensor_id = uuid.uuid4()
    with get_sync_session() as session:
        s = Sensor(
            id=sensor_id,
            controller_id=controller_id,
            name=f"{stype.value} Sensor",
            sensor_code=code,
            sensor_type=stype,
            status=SensorStatus.ACTIVE,
        )
        session.add(s)
        session.commit()
        session.refresh(s)
    return s


def helper_create_telemetry(sensor_id: uuid.UUID, value: float, unit: str) -> TelemetryReading:
    reading_id = uuid.uuid4()
    with get_sync_session() as session:
        r = TelemetryReading(
            id=reading_id,
            sensor_id=sensor_id,
            value=value,
            unit=unit,
            occurred_at=datetime.now(timezone.utc),
            metadata_={"quality": "GOOD"}
        )
        session.add(r)
        session.commit()
        session.refresh(r)
    return r


def helper_create_user(email: str, role: UserRole, organization_id: uuid.UUID = None) -> tuple[User, str]:
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            email=email,
            password_hash=get_password_hash("Secret123!"),
            name="Test User",
            role=role,
            is_active=True,
            organization_id=organization_id
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    token = create_access_token(
        subject=str(user_id),
        extra_claims={"org": str(organization_id) if organization_id else None, "role": role.value}
    )
    return user, token


def test_water_quality_api(client):
    org = helper_create_org("WQ_ORG1", "Water Quality Org 1")
    site = helper_create_site(org.id, "WQ_SITE1", "WQ Site 1")
    station = helper_create_station(site.id, "WQ_STN1", "WQ Station 1")
    ctrl = helper_create_controller(station.id, "ESP_WQ_01", "CTRL_WQ1")
    turb_sensor = helper_create_sensor(ctrl.id, "TURB_01", SensorType.TURBIDITY)
    ph_sensor = helper_create_sensor(ctrl.id, "PH_01", SensorType.PH)

    helper_create_telemetry(turb_sensor.id, 3.5, "NTU")
    helper_create_telemetry(ph_sensor.id, 7.2, "pH")

    _, token = helper_create_user("wq_user@test.com", UserRole.STATION_OPERATOR, org.id)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/stations/{station.id}/water-quality", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["station_id"] == str(station.id)
    assert data["turbidity_ntu"] == 3.5
    assert data["ph"] == 7.2
    assert data["status"] == WaterQualityStatus.SAFE.value
    assert data["is_safe"] is True
    assert data["should_trip"] is False

    # Simulate warning tier (8.5 NTU)
    helper_create_telemetry(turb_sensor.id, 8.5, "NTU")
    res_warn = client.get(f"/api/v1/stations/{station.id}/water-quality", headers=headers)
    assert res_warn.status_code == 200
    assert res_warn.json()["status"] == WaterQualityStatus.WARNING.value
    assert res_warn.json()["is_safe"] is True
    assert res_warn.json()["should_trip"] is False


    # Simulate severe contamination (>25 NTU)
    helper_create_telemetry(turb_sensor.id, 32.0, "NTU")
    res_bad = client.get(f"/api/v1/stations/{station.id}/water-quality", headers=headers)
    assert res_bad.status_code == 200
    bad_data = res_bad.json()
    assert bad_data["turbidity_ntu"] == 32.0
    assert bad_data["status"] == WaterQualityStatus.UNSAFE.value
    assert bad_data["is_safe"] is False
    assert bad_data["should_trip"] is True


def test_flow_diagnostics_api(client):
    org = helper_create_org("FLOW_ORG1", "Flow Org 1")
    site = helper_create_site(org.id, "FLOW_SITE1", "Flow Site 1")
    station = helper_create_station(site.id, "FLOW_STN1", "Flow Station 1")
    ctrl = helper_create_controller(station.id, "ESP_FLOW_01", "CTRL_FL1")
    motor = helper_create_motor(ctrl.id, "MTR_FL1", status=MotorStatus.ON)
    flow_sensor = helper_create_sensor(ctrl.id, "FLW_01", SensorType.FLOW)

    helper_create_telemetry(flow_sensor.id, 45.0, "L/min")

    _, token = helper_create_user("flow_user@test.com", UserRole.STATION_OPERATOR, org.id)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/motors/{motor.id}/flow-diagnostics", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["motor_id"] == str(motor.id)
    assert data["flow_rate_lpm"] == 45.0
    assert data["status"] == FlowSafetyStatus.NORMAL.value
    assert data["is_safe"] is True


def test_electrical_metrics_api(client):
    org = helper_create_org("ELEC_ORG1", "Elec Org 1")
    site = helper_create_site(org.id, "ELEC_SITE1", "Elec Site 1")
    station = helper_create_station(site.id, "ELEC_STN1", "Elec Station 1")
    ctrl = helper_create_controller(station.id, "ESP_ELEC_01", "CTRL_EL1")
    motor = helper_create_motor(ctrl.id, "MTR_EL1", status=MotorStatus.ON)
    curr_sensor = helper_create_sensor(ctrl.id, "CURR_01", SensorType.CURRENT)
    volt_sensor = helper_create_sensor(ctrl.id, "VOLT_01", SensorType.VOLTAGE)

    helper_create_telemetry(curr_sensor.id, 9.5, "A")
    helper_create_telemetry(volt_sensor.id, 230.0, "V")

    _, token = helper_create_user("elec_user@test.com", UserRole.STATION_OPERATOR, org.id)
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/api/v1/motors/{motor.id}/electrical-metrics", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["motor_id"] == str(motor.id)
    assert data["current_a"] == 9.5
    assert data["voltage_v"] == 230.0
    assert data["status"] == ElectricalSafetyStatus.NORMAL.value
    assert data["is_safe"] is True
    assert data["power_kw"] > 0
