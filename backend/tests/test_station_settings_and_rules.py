"""Tests for Station Settings & Automation Rules APIs (Phase 12 - Wave 2A)."""

import uuid
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
from app.models.automation_rule import (
    AutomationRuleType,
    AutomationOperator,
    AutomationAction,
    AutomationRuleStatus,
)
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
            name="Main Controller",
            controller_code=code,
            device_uid=uid,
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(ctrl)
        session.commit()
        session.refresh(ctrl)
    return ctrl


def helper_create_motor(controller_id: uuid.UUID, code: str) -> Motor:
    motor_id = uuid.uuid4()
    with get_sync_session() as session:
        m = Motor(
            id=motor_id,
            controller_id=controller_id,
            name="P1 Pump",
            motor_code=code,
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            status=MotorStatus.OFF,
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
            name="Level Sensor",
            sensor_code=code,
            sensor_type=stype,
            status=SensorStatus.ACTIVE,
        )
        session.add(s)
        session.commit()
        session.refresh(s)
    return s



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



def test_station_settings_get_and_update(client):
    org = helper_create_org("SET_ORG1", "Settings Org 1")
    site = helper_create_site(org.id, "SITE_S1", "Site S1")
    station = helper_create_station(site.id, "STN_S1", "Station S1")
    _, admin_token = helper_create_user("admin_s1@test.com", UserRole.ORGANIZATION_ADMIN, org.id)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. GET settings (lazy defaults initialized)
    res_get = client.get(f"/api/v1/stations/{station.id}/settings", headers=headers)
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["station_id"] == str(station.id)
    assert data["auto_stop_on_tank_full"] is False

    # 2. PUT settings (update thresholds)
    update_payload = {
        "auto_stop_on_tank_full": True,
        "water_level_threshold": 95.0,
        "turbidity_threshold": 15.0,
        "timezone": "Asia/Kolkata"
    }
    res_put = client.put(f"/api/v1/stations/{station.id}/settings", json=update_payload, headers=headers)
    assert res_put.status_code == 200
    put_data = res_put.json()
    assert put_data["auto_stop_on_tank_full"] is True
    assert put_data["water_level_threshold"] == 95.0
    assert put_data["turbidity_threshold"] == 15.0


def test_station_settings_rbac_and_isolation(client):
    org1 = helper_create_org("SET_ORG2", "Settings Org 2")
    org2 = helper_create_org("SET_ORG3", "Settings Org 3")
    site1 = helper_create_site(org1.id, "SITE_S2", "Site S2")
    station1 = helper_create_station(site1.id, "STN_S2", "Station S2")

    _, op_token = helper_create_user("op_s2@test.com", UserRole.STATION_OPERATOR, org1.id)
    _, foreign_admin_token = helper_create_user("for_admin@test.com", UserRole.ORGANIZATION_ADMIN, org2.id)

    # Operator can read settings
    res_op_get = client.get(f"/api/v1/stations/{station1.id}/settings", headers={"Authorization": f"Bearer {op_token}"})
    assert res_op_get.status_code == 200

    # Operator cannot update settings (HTTP 403)
    res_op_put = client.put(
        f"/api/v1/stations/{station1.id}/settings",
        json={"auto_stop_on_tank_full": True},
        headers={"Authorization": f"Bearer {op_token}"}
    )
    assert res_op_put.status_code == 403

    # Foreign tenant receives 404 (IDOR protection)
    res_idor = client.get(f"/api/v1/stations/{station1.id}/settings", headers={"Authorization": f"Bearer {foreign_admin_token}"})
    assert res_idor.status_code == 404


def test_automation_rules_crud(client):
    org = helper_create_org("RULE_ORG1", "Rule Org 1")
    site = helper_create_site(org.id, "RULE_SITE1", "Rule Site 1")
    station = helper_create_station(site.id, "RULE_STN1", "Rule Station 1")
    ctrl = helper_create_controller(station.id, "ESP_RULE_01", "CTRL_R1")
    motor = helper_create_motor(ctrl.id, "MTR_R1")
    sensor = helper_create_sensor(ctrl.id, "SNS_R1", SensorType.WATER_LEVEL)

    _, admin_token = helper_create_user("admin_rule1@test.com", UserRole.ORGANIZATION_ADMIN, org.id)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. POST /api/v1/automation-rules
    payload = {
        "station_id": str(station.id),
        "name": "High Water Level Auto-Stop",
        "description": "Stop pump when tank reaches 95%",
        "rule_type": AutomationRuleType.WATER_LEVEL.value,
        "status": AutomationRuleStatus.ACTIVE.value,
        "sensor_id": str(sensor.id),
        "operator": AutomationOperator.GREATER_THAN_OR_EQUAL.value,
        "threshold_value": 95.0,
        "threshold_unit": "%",
        "motor_id": str(motor.id),
        "action": AutomationAction.STOP_MOTOR.value
    }
    res_post = client.post("/api/v1/automation-rules", json=payload, headers=headers)
    assert res_post.status_code == 201
    rule_data = res_post.json()
    rule_id = rule_data["id"]
    assert rule_data["name"] == "High Water Level Auto-Stop"

    # 2. GET /api/v1/automation-rules?station_id=...
    res_list = client.get(f"/api/v1/automation-rules?station_id={station.id}", headers=headers)
    assert res_list.status_code == 200
    rules = res_list.json()
    assert len(rules) >= 1
    assert any(r["id"] == rule_id for r in rules)

    # 3. PUT /api/v1/automation-rules/{rule_id}
    res_put = client.put(
        f"/api/v1/automation-rules/{rule_id}",
        json={"threshold_value": 96.0, "status": AutomationRuleStatus.INACTIVE.value},
        headers=headers
    )
    assert res_put.status_code == 200
    assert res_put.json()["threshold_value"] == 96.0
    assert res_put.json()["status"] == AutomationRuleStatus.INACTIVE.value

    # 4. DELETE /api/v1/automation-rules/{rule_id}
    res_del = client.delete(f"/api/v1/automation-rules/{rule_id}", headers=headers)
    assert res_del.status_code == 204

    # 5. Verify deleted
    res_list_after = client.get(f"/api/v1/automation-rules?station_id={station.id}", headers=headers)
    assert not any(r["id"] == rule_id for r in res_list_after.json())
