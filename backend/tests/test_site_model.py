import uuid
import pytest
import asyncio
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization, OrganizationStatus
    from app.models.site import Site, SiteStatus, SiteType
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.organization import Organization, OrganizationStatus
    from backend.app.models.site import Site, SiteStatus, SiteType
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_site_tables():
    """Create all tables before running tests and drop after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_site_model_inheritance_and_metadata():
    """Verify Site model inherits from BaseModel and exists in Base.metadata."""
    assert issubclass(Site, BaseModel)
    assert "sites" in Base.metadata.tables
    table = Base.metadata.tables["sites"]
    assert "id" in table.columns
    assert "organization_id" in table.columns
    assert "name" in table.columns
    assert "site_code" in table.columns
    assert "site_type" in table.columns
    assert "location" in table.columns
    assert "timezone" in table.columns
    assert "status" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns


def test_site_creation_and_defaults_sync():
    """Verify site creation with defaults (timezone='Asia/Kolkata', status='ACTIVE', site_type='HOME')."""
    with get_sync_session() as session:
        org = Organization(
            name="Apex Water Solutions",
            organization_code="APEX-SITE-ORG"
        )
        session.add(org)
        session.flush()

        site = Site(
            organization_id=org.id,
            name="Jaipur Residence",
            site_code="HOME-001",
            location="Civil Lines, Jaipur, RJ"
        )
        session.add(site)
        session.flush()

        assert site.id is not None
        assert isinstance(site.id, uuid.UUID)
        assert site.organization_id == org.id
        assert site.name == "Jaipur Residence"
        assert site.site_code == "HOME-001"
        assert site.site_type == SiteType.HOME
        assert site.timezone == "Asia/Kolkata"
        assert site.status == SiteStatus.ACTIVE
        assert site.location == "Civil Lines, Jaipur, RJ"
        assert isinstance(site.created_at, datetime)
        assert isinstance(site.updated_at, datetime)
        site_id = site.id

    # Verify query
    with get_sync_session() as session:
        queried = session.get(Site, site_id)
        assert queried is not None
        assert queried.id == site_id
        assert queried.site_code == "HOME-001"
        assert "HOME-001" in str(queried)


def test_multi_tenant_scoped_site_code_uniqueness():
    """
    Verify multi-tenant uniqueness:
    Organization A + SITE-001 = valid
    Organization B + SITE-001 = valid
    Organization A + SITE-001 again = raises IntegrityError
    """
    with get_sync_session() as session:
        org_a = Organization(name="Org Alpha", organization_code="ORG-ALPHA-SITE")
        org_b = Organization(name="Org Beta", organization_code="ORG-BETA-SITE")
        session.add_all([org_a, org_b])
        session.flush()

        # Both organizations can have a site with the same site_code
        site_a1 = Site(
            organization_id=org_a.id,
            name="Alpha Plant",
            site_code="SITE-001",
            site_type=SiteType.FACTORY
        )
        site_b1 = Site(
            organization_id=org_b.id,
            name="Beta Plant",
            site_code="SITE-001",
            site_type=SiteType.FACTORY
        )
        session.add_all([site_a1, site_b1])
        session.flush()

        assert site_a1.id is not None
        assert site_b1.id is not None
        org_a_id = org_a.id

    # Inserting duplicate site_code in Org Alpha must fail
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            duplicate_site = Site(
                organization_id=org_a_id,
                name="Alpha Duplicate",
                site_code="SITE-001",
                site_type=SiteType.OFFICE
            )
            session.add(duplicate_site)
            session.flush()


def test_site_types_coverage():
    """Verify all defined SiteType enum values are supported."""
    site_types = [
        SiteType.HOME,
        SiteType.BUILDING,
        SiteType.FACTORY,
        SiteType.OFFICE,
        SiteType.AGRICULTURE,
        SiteType.PUMP_STATION,
        SiteType.WATER_PLANT,
        SiteType.WAREHOUSE,
        SiteType.OTHER,
    ]

    with get_sync_session() as session:
        org = Organization(name="Site Type Utility", organization_code="ORG-SITE-TYPES")
        session.add(org)
        session.flush()

        for idx, s_type in enumerate(site_types):
            s = Site(
                organization_id=org.id,
                name=f"Site {s_type.value}",
                site_code=f"TYPE-{idx:03d}",
                site_type=s_type
            )
            session.add(s)
        session.flush()
        org_id = org.id

    # Verify query back
    with get_sync_session() as session:
        sites = session.execute(
            select(Site).where(Site.organization_id == org_id)
        ).scalars().all()
        assert len(sites) == len(site_types)
        persisted_types = {s.site_type for s in sites}
        assert persisted_types == set(site_types)


def test_site_status_states():
    """Verify all SiteStatus enum values (ACTIVE, INACTIVE, SUSPENDED, MAINTENANCE)."""
    statuses = [
        (SiteStatus.ACTIVE, "STAT-001"),
        (SiteStatus.INACTIVE, "STAT-002"),
        (SiteStatus.SUSPENDED, "STAT-003"),
        (SiteStatus.MAINTENANCE, "STAT-004"),
    ]

    with get_sync_session() as session:
        org = Organization(name="Site Status Org", organization_code="ORG-SITE-STATUS")
        session.add(org)
        session.flush()

        for status, code in statuses:
            s = Site(
                organization_id=org.id,
                name=f"Site {status.value}",
                site_code=code,
                status=status
            )
            session.add(s)
        session.flush()

    with get_sync_session() as session:
        for status, code in statuses:
            s = session.execute(
                select(Site).where(Site.site_code == code)
            ).scalar_one()
            assert s.status == status


def test_organization_site_relationship_bidirectional():
    """Verify bidirectional relationship traversal: Organization.sites and Site.organization."""
    with get_sync_session() as session:
        org = Organization(
            name="Jaipur Water Authority",
            organization_code="JPR-WATER-AUTH"
        )
        session.add(org)
        session.flush()

        site1 = Site(
            organization=org,
            name="Jaipur Plant #1",
            site_code="JPR-PLT-01",
            site_type=SiteType.WATER_PLANT
        )
        site2 = Site(
            organization=org,
            name="Jaipur Pump Station A",
            site_code="JPR-PS-01",
            site_type=SiteType.PUMP_STATION
        )
        session.add_all([site1, site2])
        session.flush()

        org_id = org.id
        site1_id = site1.id

    # Verify Organization -> Sites
    with get_sync_session() as session:
        fetched_org = session.get(Organization, org_id)
        assert fetched_org is not None
        assert len(fetched_org.sites) == 2
        site_codes = [s.site_code for s in fetched_org.sites]
        assert "JPR-PLT-01" in site_codes
        assert "JPR-PS-01" in site_codes

    # Verify Site -> Organization
    with get_sync_session() as session:
        fetched_site = session.get(Site, site1_id)
        assert fetched_site is not None
        assert fetched_site.organization is not None
        assert fetched_site.organization.organization_code == "JPR-WATER-AUTH"


@pytest.mark.asyncio
async def test_site_async_crud_and_updated_at():
    """Verify async session operations and updated_at changes."""
    async with get_async_session() as session:
        org = Organization(name="Async Org For Site", organization_code="ASYNC-SITE-ORG")
        session.add(org)
        await session.flush()

        site = Site(
            organization_id=org.id,
            name="Async Site Initial",
            site_code="ASYNC-SITE-01",
            timezone="Asia/Kolkata"
        )
        session.add(site)
        await session.flush()
        site_id = site.id
        initial_updated_at = site.updated_at

    await asyncio.sleep(0.05)

    async with get_async_session() as session:
        result = await session.execute(select(Site).where(Site.id == site_id))
        site_to_update = result.scalar_one()
        site_to_update.name = "Async Site Renamed"
        site_to_update.status = SiteStatus.MAINTENANCE
        await session.flush()

        assert site_to_update.name == "Async Site Renamed"
        assert site_to_update.status == SiteStatus.MAINTENANCE
        assert site_to_update.updated_at >= initial_updated_at
