"""
HydraControl — Cross-Organization Attack Test Matrix & IDOR Protection (LOOP 4)
Simulates active attack scenarios:
1. IDOR (Insecure Direct Object Reference) attempts across tenants.
2. Cross-tenant credential manipulation.
3. Client-supplied organization_id parameter tampering.
"""
import uuid
import pytest
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_async_session, get_sync_session, get_db
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteType, SiteStatus
from app.models.station import Station, StationType, StationStatus
from app.models.controller import Controller, ControllerType, ControllerStatus
from app.models.motor import Motor, MotorType, MotorStatus
from app.models.user import User, UserRole
from app.api.deps import get_current_user, get_current_organization
from app.services.tenant import get_org_scoped_resource
from app.core.security import create_access_token, get_password_hash

# Helper test app to simulate resource retrieval under tenant isolation
attack_sim_app = FastAPI()

@attack_sim_app.get("/api/v1/test/motors/{motor_id}")
async def get_motor_endpoint(
    motor_id: uuid.UUID,
    client_org_override: uuid.UUID = None,  # Parameter simulation
    current_org: Organization = Depends(get_current_organization),
    session: AsyncSession = Depends(get_db)
):
    # Server strictly uses current_org.id, ignoring any client_org_override
    motor = await get_org_scoped_resource(session, Motor, motor_id, current_org.id)
    if motor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Motor not found"
        )
    return {
        "id": str(motor.id),
        "name": motor.name,
        "motor_code": motor.motor_code
    }



@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def seeded_data():
    with get_sync_session() as session:
        # Organization A
        org_a = Organization(
            id=uuid.uuid4(),
            name="Tenant Alpha",
            organization_code="T-ALPHA",
            status=OrganizationStatus.ACTIVE
        )
        org_b = Organization(
            id=uuid.uuid4(),
            name="Tenant Beta",
            organization_code="T-BETA",
            status=OrganizationStatus.ACTIVE
        )
        session.add_all([org_a, org_b])
        session.commit()

        # Users
        user_a = User(
            id=uuid.uuid4(),
            name="User Alpha",
            email="user_alpha@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.STATION_OPERATOR,
            is_active=True,
            organization_id=org_a.id
        )
        user_b = User(
            id=uuid.uuid4(),
            name="User Beta",
            email="user_beta@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.STATION_OPERATOR,
            is_active=True,
            organization_id=org_b.id
        )
        session.add_all([user_a, user_b])
        session.commit()

        # Site A -> Station A -> Controller A -> Motor A
        site_a = Site(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Site Alpha",
            site_code="SA-01",
            site_type=SiteType.HOME,
            status=SiteStatus.ACTIVE
        )
        session.add(site_a)
        session.commit()

        stn_a = Station(
            id=uuid.uuid4(),
            site_id=site_a.id,
            name="Station Alpha",
            station_code="STA-01",
            station_type=StationType.HOME_PUMP,
            status=StationStatus.ACTIVE
        )
        session.add(stn_a)
        session.commit()

        ctrl_a = Controller(
            id=uuid.uuid4(),
            station_id=stn_a.id,
            name="Ctrl Alpha",
            controller_code="CA-01",
            device_uid="DEV-ALPHA-99",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(ctrl_a)
        session.commit()

        motor_a = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_a.id,
            name="Motor Alpha",
            motor_code="MA-01",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        session.add(motor_a)
        session.commit()

        # Site B -> Station B -> Controller B -> Motor B
        site_b = Site(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            name="Site Beta",
            site_code="SB-01",
            site_type=SiteType.HOME,
            status=SiteStatus.ACTIVE
        )
        session.add(site_b)
        session.commit()

        stn_b = Station(
            id=uuid.uuid4(),
            site_id=site_b.id,
            name="Station Beta",
            station_code="STB-01",
            station_type=StationType.HOME_PUMP,
            status=StationStatus.ACTIVE
        )
        session.add(stn_b)
        session.commit()

        ctrl_b = Controller(
            id=uuid.uuid4(),
            station_id=stn_b.id,
            name="Ctrl Beta",
            controller_code="CB-01",
            device_uid="DEV-BETA-99",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(ctrl_b)
        session.commit()

        motor_b = Motor(
            id=uuid.uuid4(),
            controller_id=ctrl_b.id,
            name="Motor Beta",
            motor_code="MB-01",
            motor_type=MotorType.WATER_PUMP,
            status=MotorStatus.OFF
        )
        session.add(motor_b)
        session.commit()

        return {
            "org_a": org_a.id,
            "org_b": org_b.id,
            "user_a": user_a.id,
            "user_b": user_b.id,
            "motor_a": motor_a.id,
            "motor_b": motor_b.id,
        }


def test_idor_cross_organization_denial(seeded_data):
    client = TestClient(attack_sim_app)
    
    token_a = create_access_token(subject=str(seeded_data["user_a"]))
    token_b = create_access_token(subject=str(seeded_data["user_b"]))
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    motor_a_id = str(seeded_data["motor_a"])
    motor_b_id = str(seeded_data["motor_b"])

    # 1. User A requesting Motor A -> ALLOW (200)
    res = client.get(f"/api/v1/test/motors/{motor_a_id}", headers=headers_a)
    assert res.status_code == 200
    assert res.json()["id"] == motor_a_id

    # 2. User B requesting Motor B -> ALLOW (200)
    res = client.get(f"/api/v1/test/motors/{motor_b_id}", headers=headers_b)
    assert res.status_code == 200
    assert res.json()["id"] == motor_b_id

    # 3. IDOR Attack 1: User A requesting legitimate Motor B UUID -> DENY (404 Not Found)
    # Does not reveal that Motor B exists in another organization
    res = client.get(f"/api/v1/test/motors/{motor_b_id}", headers=headers_a)
    assert res.status_code == 404
    assert res.json()["detail"] == "Motor not found"

    # 4. IDOR Attack 2: User B requesting legitimate Motor A UUID -> DENY (404 Not Found)
    res = client.get(f"/api/v1/test/motors/{motor_a_id}", headers=headers_b)
    assert res.status_code == 404
    assert res.json()["detail"] == "Motor not found"


def test_parameter_tampering_denial(seeded_data):
    client = TestClient(attack_sim_app)
    token_a = create_access_token(subject=str(seeded_data["user_a"]))
    headers_a = {"Authorization": f"Bearer {token_a}"}

    motor_b_id = str(seeded_data["motor_b"])
    org_b_id = str(seeded_data["org_b"])

    # Attack: User A passes Org B's organization_id in query parameter trying to switch tenant context
    res = client.get(
        f"/api/v1/test/motors/{motor_b_id}?client_org_override={org_b_id}",
        headers=headers_a
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Motor not found"

