import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.future import select

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for Site API tests and drop after."""
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
# 1. AUTHENTICATION & RBAC TESTS FOR CREATE (POST /sites)
# ============================================================================

def test_create_site_unauthenticated(client: TestClient):
    payload = {"name": "Unauth Site", "site_code": "SITE-UNAUTH"}
    res = client.post("/api/v1/sites", json=payload)
    assert res.status_code == 401

def test_create_site_rbac_roles(client: TestClient):
    org = helper_create_org("SITE-ORG-01", "Site Org One")
    _, super_token = helper_create_user("super.site@example.com", UserRole.SUPER_ADMIN, org.id)
    _, org_admin_token = helper_create_user("orgadmin.site@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, site_mgr_token = helper_create_user("sitemgr.site@example.com", UserRole.SITE_MANAGER, org.id)
    _, operator_token = helper_create_user("operator.site@example.com", UserRole.STATION_OPERATOR, org.id)
    _, viewer_token = helper_create_user("viewer.site@example.com", UserRole.VIEWER, org.id)

    payload = {"name": "Factory Alpha", "site_code": "FACT-01", "site_type": "FACTORY"}

    # Forbidden roles
    assert client.post("/api/v1/sites", json=payload, headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403
    assert client.post("/api/v1/sites", json=payload, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Allowed roles
    res_mgr = client.post("/api/v1/sites", json=payload, headers={"Authorization": f"Bearer {site_mgr_token}"})
    assert res_mgr.status_code == 201
    assert res_mgr.json()["site_code"] == "FACT-01"
    assert res_mgr.json()["organization_id"] == str(org.id)

    res_admin = client.post("/api/v1/sites", json={"name": "Factory Beta", "site_code": "FACT-02"}, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin.status_code == 201

    res_super = client.post("/api/v1/sites", json={"name": "Factory Gamma", "site_code": "FACT-03", "organization_id": str(org.id)}, headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 201

def test_create_site_tenant_lockdown(client: TestClient):
    org1 = helper_create_org("LOCK-ORG-01", "Lock Org 1")
    org2 = helper_create_org("LOCK-ORG-02", "Lock Org 2")

    _, user1_token = helper_create_user("user1.lock@example.com", UserRole.ORGANIZATION_ADMIN, org1.id)

    # User 1 attempts to create site specifying Org 2 ID in payload -> Server forces site into Org 1
    payload = {
        "organization_id": str(org2.id),
        "name": "Tampered Site",
        "site_code": "TAMP-01"
    }
    res = client.post("/api/v1/sites", json=payload, headers={"Authorization": f"Bearer {user1_token}"})
    assert res.status_code == 201
    assert res.json()["organization_id"] == str(org1.id)  # Derived server-side from current user

def test_create_site_duplicate_code(client: TestClient):
    org = helper_create_org("DUP-ORG-01", "Dup Org")
    _, token = helper_create_user("admin.dup@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    payload = {"name": "Site One", "site_code": "DUP-SITE-01"}
    res1 = client.post("/api/v1/sites", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    res2 = client.post("/api/v1/sites", json={"name": "Site Two", "site_code": "dup-site-01"}, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409
    assert "already exists in this organization" in res2.json()["detail"]

# ============================================================================
# 2. LIST SITES (GET /sites) & TENANT ISOLATION
# ============================================================================

def test_list_sites_tenant_isolation(client: TestClient):
    org_a = helper_create_org("LIST-ORG-A", "List Org A")
    org_b = helper_create_org("LIST-ORG-B", "List Org B")

    _, super_token = helper_create_user("super.listsite@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.lista@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    # Create sites in Org A & Org B
    client.post("/api/v1/sites", json={"name": "Site A1", "site_code": "SA1", "organization_id": str(org_a.id)}, headers={"Authorization": f"Bearer {super_token}"})
    client.post("/api/v1/sites", json={"name": "Site B1", "site_code": "SB1", "organization_id": str(org_b.id)}, headers={"Authorization": f"Bearer {super_token}"})

    # Admin A lists sites -> receives ONLY Site A1
    res_a = client.get("/api/v1/sites", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_a.status_code == 200
    codes_a = [s["site_code"] for s in res_a.json()]
    assert "SA1" in codes_a
    assert "SB1" not in codes_a

    # SUPER_ADMIN lists sites -> receives all or filters by org
    res_super_all = client.get("/api/v1/sites", headers={"Authorization": f"Bearer {super_token}"})
    assert res_super_all.status_code == 200
    assert len(res_super_all.json()) >= 2

    res_super_b = client.get(f"/api/v1/sites?organization_id={org_b.id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_super_b.status_code == 200
    codes_b = [s["site_code"] for s in res_super_b.json()]
    assert "SB1" in codes_b
    assert "SA1" not in codes_b

# ============================================================================
# 3. RETRIEVE SITE (GET /sites/{id}) & IDOR / OPERATIONAL STATUS CHECKS
# ============================================================================

def test_get_site_idor_protection(client: TestClient):
    org_a = helper_create_org("GET-ORG-A", "Get Org A")
    org_b = helper_create_org("GET-ORG-B", "Get Org B")

    _, super_token = helper_create_user("super.getsite@example.com", UserRole.SUPER_ADMIN, org_a.id)
    _, admin_a_token = helper_create_user("admin.geta@example.com", UserRole.ORGANIZATION_ADMIN, org_a.id)

    res_b = client.post("/api/v1/sites", json={"name": "Private Org B Site", "site_code": "PRIV-B", "organization_id": str(org_b.id)}, headers={"Authorization": f"Bearer {super_token}"})
    site_b_id = uuid.UUID(res_b.json()["id"])

    # Admin A attempts IDOR access to Org B site -> 404 Not Found
    res_idor = client.get(f"/api/v1/sites/{site_b_id}", headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res_idor.status_code == 404
    assert res_idor.json()["detail"] == "Site not found"

def test_get_site_operational_status_policies(client: TestClient):
    org = helper_create_org("STATUS-ORG", "Status Org")
    _, super_token = helper_create_user("super.status@example.com", UserRole.SUPER_ADMIN, org.id)
    _, operator_token = helper_create_user("operator.status@example.com", UserRole.STATION_OPERATOR, org.id)
    _, manager_token = helper_create_user("manager.status@example.com", UserRole.SITE_MANAGER, org.id)

    # Inactive Site
    res_inact = client.post("/api/v1/sites", json={"name": "Inactive Site", "site_code": "INACT-01", "status": "INACTIVE", "organization_id": str(org.id)}, headers={"Authorization": f"Bearer {super_token}"})
    inact_id = uuid.UUID(res_inact.json()["id"])
    assert client.get(f"/api/v1/sites/{inact_id}", headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403

    # Maintenance Site
    res_maint = client.post("/api/v1/sites", json={"name": "Maintenance Site", "site_code": "MAINT-01", "status": "MAINTENANCE", "organization_id": str(org.id)}, headers={"Authorization": f"Bearer {super_token}"})
    maint_id = uuid.UUID(res_maint.json()["id"])
    
    assert client.get(f"/api/v1/sites/{maint_id}", headers={"Authorization": f"Bearer {operator_token}"}).status_code == 403
    assert client.get(f"/api/v1/sites/{maint_id}", headers={"Authorization": f"Bearer {manager_token}"}).status_code == 200

# ============================================================================
# 4. UPDATE SITE (PUT/PATCH /sites/{id})
# ============================================================================

def test_update_site(client: TestClient):
    org = helper_create_org("UPD-ORG-SITE", "Upd Org Site")
    _, super_token = helper_create_user("super.updsite@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.updsite@example.com", UserRole.ORGANIZATION_ADMIN, org.id)
    _, viewer_token = helper_create_user("viewer.updsite@example.com", UserRole.VIEWER, org.id)

    res = client.post("/api/v1/sites", json={"name": "Old Site Name", "site_code": "OLD-01", "organization_id": str(org.id)}, headers={"Authorization": f"Bearer {super_token}"})
    site_id = uuid.UUID(res.json()["id"])

    # Viewer cannot update -> 403 Forbidden
    assert client.patch(f"/api/v1/sites/{site_id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 403

    # Org Admin update -> 200 OK
    res_upd = client.put(f"/api/v1/sites/{site_id}", json={"name": "New Site Name", "site_code": "NEW-01", "location": "Building 5"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_upd.status_code == 200
    assert res_upd.json()["name"] == "New Site Name"
    assert res_upd.json()["site_code"] == "NEW-01"
    assert res_upd.json()["location"] == "Building 5"

# ============================================================================
# 5. DELETE SITE (DELETE /sites/{id}) & RESTRICT CHECKS
# ============================================================================

def test_delete_site_success(client: TestClient):
    org = helper_create_org("DEL-ORG-SITE", "Del Org Site")
    _, super_token = helper_create_user("super.delsite@example.com", UserRole.SUPER_ADMIN, org.id)
    _, admin_token = helper_create_user("admin.delsite@example.com", UserRole.ORGANIZATION_ADMIN, org.id)

    res = client.post("/api/v1/sites", json={"name": "Site To Delete", "site_code": "DEL-SITE-01", "organization_id": str(org.id)}, headers={"Authorization": f"Bearer {super_token}"})
    site_id = uuid.UUID(res.json()["id"])

    res_del = client.delete(f"/api/v1/sites/{site_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_del.status_code == 204

    res_get = client.get(f"/api/v1/sites/{site_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_get.status_code == 404

def test_delete_site_with_dependent_stations_fails(client: TestClient):
    org = helper_create_org("STN-ORG-SITE", "Stn Org Site")
    _, super_token = helper_create_user("super.stnsite@example.com", UserRole.SUPER_ADMIN, org.id)

    res_site = client.post("/api/v1/sites", json={"name": "Site With Station", "site_code": "STN-SITE-01", "organization_id": str(org.id)}, headers={"Authorization": f"Bearer {super_token}"})
    site_id = uuid.UUID(res_site.json()["id"])

    # Attach dependent station in DB
    with get_sync_session() as session:
        stn = Station(
            id=uuid.uuid4(),
            site_id=site_id,
            name="Main Pump Station",
            station_code="STN-01",
            station_type=StationType.HOME_PUMP,
            status=StationStatus.ACTIVE
        )
        session.add(stn)
        session.commit()

    # Delete site fails with 400 Bad Request
    res_del = client.delete(f"/api/v1/sites/{site_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete site with active stations" in res_del.json()["detail"]
