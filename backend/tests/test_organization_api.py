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
from app.core.security import create_access_token, get_password_hash

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create database tables for organization API tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

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
# 1. AUTHENTICATION & RBAC TESTS FOR CREATE (POST /organizations)
# ============================================================================

def test_create_organization_unauthenticated(client: TestClient):
    payload = {"name": "Test Org", "organization_code": "ORG-UNAUTH"}
    res = client.post("/api/v1/organizations", json=payload)
    assert res.status_code == 401

def test_create_organization_rbac_roles(client: TestClient):
    _, super_token = helper_create_user("superadmin.org@example.com", UserRole.SUPER_ADMIN)
    _, org_admin_token = helper_create_user("orgadmin.org@example.com", UserRole.ORGANIZATION_ADMIN)
    _, operator_token = helper_create_user("operator.org@example.com", UserRole.STATION_OPERATOR)

    payload = {"name": "Super Admin Org", "organization_code": "ORG-SUPER-01"}

    # Non-SUPER_ADMIN forbidden
    res_org_admin = client.post("/api/v1/organizations", json=payload, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_org_admin.status_code == 403

    res_operator = client.post("/api/v1/organizations", json=payload, headers={"Authorization": f"Bearer {operator_token}"})
    assert res_operator.status_code == 403

    # SUPER_ADMIN allowed
    res_super = client.post("/api/v1/organizations", json=payload, headers={"Authorization": f"Bearer {super_token}"})
    assert res_super.status_code == 201
    data = res_super.json()
    assert data["name"] == "Super Admin Org"
    assert data["organization_code"] == "ORG-SUPER-01"
    assert data["status"] == "ACTIVE"
    assert "id" in data

def test_create_organization_duplicate_code(client: TestClient):
    _, super_token = helper_create_user("superadmin.dup@example.com", UserRole.SUPER_ADMIN)

    payload = {"name": "First Org", "organization_code": "DUP-CODE-01"}
    res1 = client.post("/api/v1/organizations", json=payload, headers={"Authorization": f"Bearer {super_token}"})
    assert res1.status_code == 201

    payload_dup = {"name": "Second Org", "organization_code": "dup-code-01"}  # case-insensitive check
    res2 = client.post("/api/v1/organizations", json=payload_dup, headers={"Authorization": f"Bearer {super_token}"})
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]

def test_create_organization_validation(client: TestClient):
    _, super_token = helper_create_user("superadmin.val@example.com", UserRole.SUPER_ADMIN)

    # Empty name
    res1 = client.post("/api/v1/organizations", json={"name": "", "organization_code": "VAL-01"}, headers={"Authorization": f"Bearer {super_token}"})
    assert res1.status_code == 422

    # Blank code
    res2 = client.post("/api/v1/organizations", json={"name": "Valid Name", "organization_code": "   "}, headers={"Authorization": f"Bearer {super_token}"})
    assert res2.status_code == 422

# ============================================================================
# 2. LIST ORGANIZATIONS (GET /organizations) & TENANT ISOLATION
# ============================================================================

def test_list_organizations_tenant_isolation(client: TestClient):
    _, super_token = helper_create_user("super.list@example.com", UserRole.SUPER_ADMIN)

    # Create Org A and Org B
    res_a = client.post("/api/v1/organizations", json={"name": "Tenant Alpha", "organization_code": "ALPHA-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_a_id = uuid.UUID(res_a.json()["id"])

    res_b = client.post("/api/v1/organizations", json={"name": "Tenant Beta", "organization_code": "BETA-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_b_id = uuid.UUID(res_b.json()["id"])

    # Create Org Admin for Org A
    _, user_a_token = helper_create_user("user.alpha@example.com", UserRole.ORGANIZATION_ADMIN, organization_id=org_a_id)

    # SUPER_ADMIN gets all organizations
    super_list = client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {super_token}"})
    assert super_list.status_code == 200
    all_orgs = super_list.json()
    org_codes = [o["organization_code"] for o in all_orgs]
    assert "ALPHA-01" in org_codes
    assert "BETA-01" in org_codes

    # Org Admin A gets ONLY Tenant Alpha
    user_a_list = client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {user_a_token}"})
    assert user_a_list.status_code == 200
    a_orgs = user_a_list.json()
    assert len(a_orgs) == 1
    assert a_orgs[0]["id"] == str(org_a_id)
    assert a_orgs[0]["organization_code"] == "ALPHA-01"

# ============================================================================
# 3. RETRIEVE ORGANIZATION (GET /organizations/{id}) & IDOR PROTECTION
# ============================================================================

def test_get_organization_by_id(client: TestClient):
    _, super_token = helper_create_user("super.get@example.com", UserRole.SUPER_ADMIN)

    res_a = client.post("/api/v1/organizations", json={"name": "Org Gamma", "organization_code": "GAMMA-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_a_id = uuid.UUID(res_a.json()["id"])

    res_b = client.post("/api/v1/organizations", json={"name": "Org Delta", "organization_code": "DELTA-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_b_id = uuid.UUID(res_b.json()["id"])

    _, user_a_token = helper_create_user("admin.gamma@example.com", UserRole.ORGANIZATION_ADMIN, organization_id=org_a_id)

    # User A accesses Org Gamma -> 200 OK
    res_own = client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {user_a_token}"})
    assert res_own.status_code == 200
    assert res_own.json()["organization_code"] == "GAMMA-01"

    # User A attempts IDOR access to Org Delta -> 404 Not Found
    res_foreign = client.get(f"/api/v1/organizations/{org_b_id}", headers={"Authorization": f"Bearer {user_a_token}"})
    assert res_foreign.status_code == 404
    assert res_foreign.json()["detail"] == "Organization not found"

    # SUPER_ADMIN accesses Org Delta -> 200 OK
    res_super_b = client.get(f"/api/v1/organizations/{org_b_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_super_b.status_code == 200
    assert res_super_b.json()["organization_code"] == "DELTA-01"

# ============================================================================
# 4. UPDATE ORGANIZATION (PUT/PATCH /organizations/{id})
# ============================================================================

def test_update_organization(client: TestClient):
    _, super_token = helper_create_user("super.upd@example.com", UserRole.SUPER_ADMIN)

    res = client.post("/api/v1/organizations", json={"name": "Original Name", "organization_code": "ORIG-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_id = uuid.UUID(res.json()["id"])

    _, org_admin_token = helper_create_user("admin.orig@example.com", UserRole.ORGANIZATION_ADMIN, organization_id=org_id)
    _, viewer_token = helper_create_user("viewer.orig@example.com", UserRole.VIEWER, organization_id=org_id)

    # VIEWER cannot update -> 403 Forbidden
    res_viewer = client.patch(f"/api/v1/organizations/{org_id}", json={"name": "Hacked Name"}, headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_viewer.status_code == 403

    # ORGANIZATION_ADMIN can update their own org -> 200 OK
    res_admin = client.put(f"/api/v1/organizations/{org_id}", json={"name": "Updated Org Name", "organization_code": "UPDATED-01"}, headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin.status_code == 200
    assert res_admin.json()["name"] == "Updated Org Name"
    assert res_admin.json()["organization_code"] == "UPDATED-01"

def test_update_organization_cross_org_idor_denial(client: TestClient):
    _, super_token = helper_create_user("super.upd2@example.com", UserRole.SUPER_ADMIN)

    res_a = client.post("/api/v1/organizations", json={"name": "Org Epsilon", "organization_code": "EPS-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_a_id = uuid.UUID(res_a.json()["id"])

    res_b = client.post("/api/v1/organizations", json={"name": "Org Zeta", "organization_code": "ZETA-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_b_id = uuid.UUID(res_b.json()["id"])

    _, admin_a_token = helper_create_user("admin.eps@example.com", UserRole.ORGANIZATION_ADMIN, organization_id=org_a_id)

    # Admin A attempts to update Org Zeta -> 404 Not Found
    res = client.patch(f"/api/v1/organizations/{org_b_id}", json={"name": "Tampered Name"}, headers={"Authorization": f"Bearer {admin_a_token}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Organization not found"

# ============================================================================
# 5. DELETE ORGANIZATION (DELETE /organizations/{id})
# ============================================================================

def test_delete_organization(client: TestClient):
    _, super_token = helper_create_user("super.del@example.com", UserRole.SUPER_ADMIN)

    res = client.post("/api/v1/organizations", json={"name": "Org To Delete", "organization_code": "DEL-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_id = uuid.UUID(res.json()["id"])

    _, org_admin_token = helper_create_user("admin.del@example.com", UserRole.ORGANIZATION_ADMIN, organization_id=org_id)

    # Non-SUPER_ADMIN forbidden
    res_admin_del = client.delete(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {org_admin_token}"})
    assert res_admin_del.status_code == 403

    # SUPER_ADMIN delete success -> 204 No Content
    res_super_del = client.delete(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_super_del.status_code == 204

    # Subsequent GET returns 404
    res_get = client.get(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_get.status_code == 404

def test_delete_organization_with_dependent_sites_fails(client: TestClient):
    _, super_token = helper_create_user("super.delsite@example.com", UserRole.SUPER_ADMIN)

    res_org = client.post("/api/v1/organizations", json={"name": "Org With Site", "organization_code": "SITE-ORG-01"}, headers={"Authorization": f"Bearer {super_token}"})
    org_id = uuid.UUID(res_org.json()["id"])

    # Attach site in DB
    with get_sync_session() as session:
        site = Site(
            id=uuid.uuid4(),
            name="Plant 1",
            site_code="SITE-001",
            organization_id=org_id,
            site_type=SiteType.FACTORY,
            status=SiteStatus.ACTIVE
        )
        session.add(site)
        session.commit()

    # Attempt to delete org -> 400 Bad Request
    res_del = client.delete(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert res_del.status_code == 400
    assert "Cannot delete organization with active sites" in res_del.json()["detail"]
