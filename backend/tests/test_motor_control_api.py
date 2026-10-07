import pytest
import uuid
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


def helper_create_user(email: str, role: UserRole, org_id: uuid.UUID = None) -> tuple[User, str]:
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            email=email,
            password_hash=get_password_hash("SecretPass123!"),
            name=f"User {email}",
            role=role,
            organization_id=org_id,
            is_active=True
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "role": user.role.value,
            "organization_id": str(user.organization_id) if user.organization_id else None
        }
    )
    return user, token


def helper_create_test_hierarchy(prefix: str, site_status: SiteStatus = SiteStatus.ACTIVE, motor_status: MotorStatus = MotorStatus.OFF):
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name=f"{prefix} Org",
            organization_code=f"{prefix}_ORG",
            status=OrganizationStatus.ACTIVE
        )
        session.add(org)

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name=f"{prefix} Site",
            site_code=f"{prefix}_SITE",
            site_type=SiteType.HOME,
            status=site_status
        )
        session.add(site)

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name=f"{prefix} Station",
            station_code=f"{prefix}_STN",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE
        )
        session.add(station)

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name=f"{prefix} Controller",
            controller_code=f"{prefix}_CTRL",
            device_uid=f"{prefix}-HW-UID-CTRL",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(controller)

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name=f"{prefix} Pump",
            motor_code="PUMP_MAIN",
            motor_type=MotorType.WATER_PUMP,
            status=motor_status,
            rated_power=5.5
        )
        session.add(motor)

        session.commit()
        return org, site, station, controller, motor


def test_start_motor_authenticated_success(client: TestClient):
    org, site, station, controller, motor = helper_create_test_hierarchy("START_API", motor_status=MotorStatus.OFF)
    _, token = helper_create_user("operator_start@example.com", UserRole.SITE_MANAGER, org.id)

    res = client.post(
        f"/api/v1/motors/{motor.id}/start",
        json={"payload": {"duration_min": 15}},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["motor_id"] == str(motor.id)
    assert data["command_type"] == "START"
    assert data["status"] in ("SENT", "PENDING")
    assert "id" in data
    assert "requested_at" in data


def test_stop_motor_authenticated_success(client: TestClient):
    org, site, station, controller, motor = helper_create_test_hierarchy("STOP_API", motor_status=MotorStatus.ON)
    _, token = helper_create_user("operator_stop@example.com", UserRole.SITE_MANAGER, org.id)

    res = client.post(
        f"/api/v1/motors/{motor.id}/stop",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["motor_id"] == str(motor.id)
    assert data["command_type"] == "STOP"


def test_emergency_stop_motor_authenticated_success(client: TestClient):
    org, site, station, controller, motor = helper_create_test_hierarchy("ESTOP_API", motor_status=MotorStatus.FAULT)
    _, token = helper_create_user("operator_estop@example.com", UserRole.SITE_MANAGER, org.id)

    res = client.post(
        f"/api/v1/motors/{motor.id}/emergency-stop",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["command_type"] == "EMERGENCY_STOP"


def test_motor_command_unauthenticated_rejected(client: TestClient):
    fake_id = uuid.uuid4()
    res = client.post(f"/api/v1/motors/{fake_id}/start")
    assert res.status_code == 401


def test_motor_command_unauthorized_role_rejected(client: TestClient):
    org, _, _, _, motor = helper_create_test_hierarchy("VIEWER_BLOCKED")
    _, viewer_token = helper_create_user("viewer_user@example.com", UserRole.VIEWER, org.id)

    res = client.post(
        f"/api/v1/motors/{motor.id}/start",
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res.status_code == 403


def test_motor_command_cross_organization_returns_404(client: TestClient):
    org_a, _, _, _, motor_a = helper_create_test_hierarchy("ORG_A_API")
    org_b, _, _, _, _ = helper_create_test_hierarchy("ORG_B_API")
    _, user_b_token = helper_create_user("user_b_actor@example.com", UserRole.SITE_MANAGER, org_b.id)

    # User in Org B tries to start motor in Org A -> 404 Not Found (IDOR protection)
    res = client.post(
        f"/api/v1/motors/{motor_a.id}/start",
        headers={"Authorization": f"Bearer {user_b_token}"}
    )
    assert res.status_code == 404


def test_motor_command_suspended_site_returns_403(client: TestClient):
    org, _, _, _, motor = helper_create_test_hierarchy("SUSP_SITE_API", site_status=SiteStatus.SUSPENDED)
    _, token = helper_create_user("user_susp@example.com", UserRole.SITE_MANAGER, org.id)

    res = client.post(
        f"/api/v1/motors/{motor.id}/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 403


def test_motor_start_rejected_when_motor_offline(client: TestClient):
    org, _, _, _, motor = helper_create_test_hierarchy("OFFLINE_MOTOR_API", motor_status=MotorStatus.OFFLINE)
    _, token = helper_create_user("user_off_m@example.com", UserRole.SITE_MANAGER, org.id)

    res = client.post(
        f"/api/v1/motors/{motor.id}/start",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "OFFLINE" in res.json()["detail"]


def test_list_and_get_motor_command_history(client: TestClient):
    org, _, _, _, motor = helper_create_test_hierarchy("HIST_API", motor_status=MotorStatus.OFF)
    _, token = helper_create_user("user_hist@example.com", UserRole.SITE_MANAGER, org.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Issue START and STOP commands
    res_start = client.post(f"/api/v1/motors/{motor.id}/start", headers=headers)
    cmd_id = res_start.json()["id"]

    client.post(f"/api/v1/motors/{motor.id}/stop", headers=headers)

    # List commands for motor
    res_list = client.get(f"/api/v1/motors/{motor.id}/commands", headers=headers)
    assert res_list.status_code == 200
    commands = res_list.json()
    assert len(commands) >= 2

    # Get single command detail
    res_detail = client.get(f"/api/v1/motors/commands/{cmd_id}", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == cmd_id
