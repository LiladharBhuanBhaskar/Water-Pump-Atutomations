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
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for Station API tests and drop after."""
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

def helper_create_site(org_id: uuid.UUID, code: str, name: str, status: SiteStatus = SiteStatus.ACTIVE) -> Site:
    site_id = uuid.uuid4()
    with get_sync_session() as session:
        site = Site(
            id=site_id,
            organization_id=org_id,
            name=name,
            site_code=code,
            site_type=SiteType.HOME,
            status=status
        )
        session.add(site)
        session.commit()
        session.refresh(site)
    return site

def helper_create_user(email: str, role: UserRole, organization_id: uuid.UUID = None) -> tuple[User, str]:
    user_id = uuid.uuid4()
    with get_sync_session() as session:
        user = User(
            id=user_id,
            name=f"User {role.value}",
            email=email,
            password_hash=get_password_hash("password123"),
            role=role,
            is_active=True,
            organization_id=organization_id
        )
        session.add(user)
        session.commit()
    token = create_access_token(subject=str(user_id))
    return user, token

# ============================================================================
# 1. AUTHENTICATION & RBAC TESTS FOR CREATE (POST /stations)
# ============================================================================

def test_create_station_unauthenticated(client: TestClient):
    payload = {"site_id": str(uuid.uuid4()), "name": "Unauth Stn", "station_code": "STN-UNAUTH"}
    res = client.post("/api/v1/stations", json=payload)
    assert res.status_code == 401

def test_create_station_rbac_roles(client: TestClient):
    org = helper_create_org("STN-ORG-01", "Station Org One")
    site = helper_create_site(org.id, "SITE-STN-01", "Site Stn 1")

    _, super_token = helper_create_user("super.stn@example.com", UserRole.SUPER_ADMIN, org.id)
    _, org_admin_token = helper_create_user("orgadmin.stn@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, site_mgr_token = helper_create_user("sitemgr.stn@example.com", UserRole.SITE_MANAGER, org.id)
    _, operator_token = helper_create_user("operator.stn@example.com", UserRole.STATION_OPERATOR, org.id)
    _, viewer_token = helper_create_user("viewer.stn@example.com", UserRole.VIEWER, org.id)

    payload = {
        "site_id": str(site.id),
        "name": "Main Pump Station",
        "station_code": "PUMP-01",
        "station_type": "HOME_PUMP"
    }

    # Forbidden roles
    assert client.post("/api/v1/stations", json=payload, headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403
    assert client.post("/api/v1/stations", json=payload, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Allowed roles
    res_mgr = client.post("/api/v1/stations", json=payload, headers={"Authorization": f"Bearer {site_mgr_token}"})
    assert res_mgr.status_code == 201
    assert res_mgr.json()["station_code"] == "PUMP-01"
    assert res_mgr.json()["site_id"] == str(site.id)

    res_admin = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "Borewell Station", "station_code": "BORE-01"}, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin.status_code == 201

    res_super = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "RO Station", "station_code": "RO-01"}, headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 201

def test_create_station_foreign_site_isolation(client: TestClient):
    org1 = helper_create_org("STN-LOCK-01", "Stn Lock Org 1")
    site1 = helper_create_site(org1.id, "SITE-LOCK-01", "Site Lock 1")

    org2 = helper_create_org("STN-LOCK-02", "Stn Lock Org 2")
    site2 = helper_create_site(org2.id, "SITE-LOCK-02", "Site Lock 2")

    _, user1_token = helper_create_user("user1.stnlock@example.com", UserRole.ORGANIZATION_ADMIN, org1.id)

    # User 1 from Org 1 attempts to create station under Site 2 (Org 2) -> 404 Not Found
    payload = {
        "site_id": str(site2.id),
        "name": "Tampered Station",
        "station_code": "TAMP-STN-01"
    }
    res = client.post("/api/v1/stations", json=payload, headers={"Authorization": f"Bearer {user1_token}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Site not found"

def test_create_station_duplicate_code(client: TestClient):
    org = helper_create_org("DUP-STN-ORG", "Dup Stn Org")
    site = helper_create_site(org.id, "DUP-STN-SITE", "Dup Stn Site")
    _, token = helper_create_user("admin.dupstn@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    payload = {"site_id": str(site.id), "name": "Station One", "station_code": "DUP-STN-01"}
    res1 = client.post("/api/v1/stations", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    res2 = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "Station Two", "station_code": "dup-stn-01"}, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409
    assert "already exists in this site" in res2.json()["detail"]

# ============================================================================
# 2. LIST STATIONS (GET /stations) & TENANT/SITE ISOLATION
# ============================================================================

def test_list_stations_tenant_isolation(client: TestClient):
    org_a = helper_create_org("LIST-STN-A", "List Stn Org A")
    site_a = helper_create_site(org_a.id, "SA-01", "Site A")

    org_b = helper_create_org("LIST-STN-B", "List Stn Org B")
    site_b = helper_create_site(org_b.id, "SB-01", "Site B")

    _, super_token = helper_create_user("super.liststn@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.liststna@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    client.post("/api/v1/stations", json={"site_id": str(site_a.id), "name": "Station A1", "station_code": "STA1"}, headers={"Authorization": f"Bearer {super_token}"})
    client.post("/api/v1/stations", json={"site_id": str(site_b.id), "name": "Station B1", "station_code": "STB1"}, headers={"Authorization": f"Bearer {super_token}"})

    # User A lists stations -> receives ONLY Station A1
    res_a = client.get("/api/v1/stations", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a.status_code == 200
    codes_a = [s["station_code"] for s in res_a.json()]
    assert "STA1" in codes_a
    assert "STB1" not in codes_a

    # User A filters by foreign site_id -> empty list
    res_a_foreign = client.get(f"/api/v1/stations?site_id={site_b.id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a_foreign.status_code == 200
    assert res_a_foreign.json() == []

# ============================================================================
# 3. RETRIEVE STATION (GET /stations/{id}) & IDOR / SITE LIFECYCLE CHECKS
# ============================================================================

def test_get_station_idor_protection(client: TestClient):
    org_a = helper_create_org("GET-STN-A", "Get Stn Org A")
    site_a = helper_create_site(org_a.id, "GSA-01", "Get Site A")

    org_b = helper_create_org("GET-STN-B", "Get Stn Org B")
    site_b = helper_create_site(org_b.id, "GSB-01", "Get Site B")

    _, super_token = helper_create_user("super.getstn@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.getstna@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    res_b = client.post("/api/v1/stations", json={"site_id": str(site_b.id), "name": "Private Station B", "station_code": "PRSTB"}, headers={"Authorization": f"Bearer {super_token}"})
    stn_b_id = uuid.UUID(res_b.json()["id"])

    # Admin A attempts IDOR access to Org B station -> 404 Not Found
    res_idor = client.get(f"/api/v1/stations/{stn_b_id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Station not found"

def test_get_station_parent_site_operational_status(client: TestClient):
    org = helper_create_org("STN-STAT-ORG", "Stn Stat Org")
    site = helper_create_site(org.id, "INACT-SITE", "Active Site Initially", status=SiteStatus.ACTIVE)

    _, super_token = helper_create_user("super.stnstat@example.com", UserRole.SUPER_ADMIN, org.id)
    _, operator_token = helper_create_user("operator.stnstat@example.com", UserRole.STATION_OPERATOR, org.id)

    res_stn = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "Inactive Parent Stn", "station_code": "INACT-STN"}, headers={"Authorization": f"Bearer {super_token}"})
    stn_id = uuid.UUID(res_stn.json()["id"])

    # Update site to INACTIVE directly in DB
    with get_sync_session() as session:
        db_site = session.get(Site, site.id)
        db_site.status = SiteStatus.INACTIVE
        session.commit()

    # Access station under inactive site -> 403 Forbidden
    res = client.get(f"/api/v1/stations/{stn_id}", headers={"Authorization": f"Bearer {operator_token}"})
    assert res.status_code == 403
    assert "Site is inactive" in res.json()["detail"]

# ============================================================================
# 4. UPDATE STATION (PUT/PATCH /stations/{id})
# ============================================================================

def test_update_station(client: TestClient):
    org = helper_create_org("UPD-STN-ORG", "Upd Stn Org")
    site = helper_create_site(org.id, "UPD-STN-SITE", "Upd Stn Site")

    _, super_token = helper_create_user("super.updstn@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.updstn@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, viewer_token = helper_create_user("viewer.updstn@example.com", UserRole.VIEWER, org.id)

    res = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "Old Station Name", "station_code": "OLD-STN"}, headers={"Authorization": f"Bearer {super_token}"})
    stn_id = uuid.UUID(res.json()["id"])

    # Viewer cannot update -> 403 Forbidden
    assert client.patch(f"/api/v1/stations/{stn_id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Org Admin update -> 200 OK
    res_upd = client.put(f"/api/v1/stations/{stn_id}", json={"name": "New Station Name", "station_code": "NEW-STN", "description": "Updated pump station"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_upd.status_code == 200
    assert res_upd.json()["name"] == "New Station Name"
    assert res_upd.json()["station_code"] == "NEW-STN"
    assert res_upd.json()["description"] == "Updated pump station"

# ============================================================================
# 5. DELETE STATION (DELETE /stations/{id}) & RESTRICT CHECKS
# ============================================================================

def test_delete_station_success(client: TestClient):
    org = helper_create_org("DEL-STN-ORG", "Del Stn Org")
    site = helper_create_site(org.id, "DEL-STN-SITE", "Del Stn Site")

    _, super_token = helper_create_user("super.delstn@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.delstn@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    res = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "Station To Delete", "station_code": "DEL-STN-01"}, headers={"Authorization": f"Bearer {super_token}"})
    stn_id = uuid.UUID(res.json()["id"])

    res_del = client.delete(f"/api/v1/stations/{stn_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_del.status_code == 204

    res_get = client.get(f"/api/v1/stations/{stn_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_get.status_code == 404

def test_delete_station_with_dependent_controllers_fails(client: TestClient):
    org = helper_create_org("CTRL-STN-ORG", "Ctrl Stn Org")
    site = helper_create_site(org.id, "CTRL-STN-SITE", "Ctrl Stn Site")

    _, super_token = helper_create_user("super.ctrlstn@example.com", UserRole.SUPER_ADMIN, org.id)

    res_stn = client.post("/api/v1/stations", json={"site_id": str(site.id), "name": "Station With Controller", "station_code": "CTRL-STN-01"}, headers={"Authorization": f"Bearer {super_token}"})
    stn_id = uuid.UUID(res_stn.json()["id"])

    # Attach dependent controller in DB
    with get_sync_session() as session:
        ctrl = Controller(
            id=uuid.uuid4(),
            station_id=stn_id,
            name="Test Controller",
            device_uid=f"DEV-UID-{uuid.uuid4().hex[:8]}",
            controller_code="CTRL-01",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE
        )
        session.add(ctrl)
        session.commit()

    # Delete station fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/stations/{stn_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete station with active controllers" in res_del.json()["detail"]
