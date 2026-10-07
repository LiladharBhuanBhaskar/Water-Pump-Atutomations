import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

try:
    from app.db.base import Base, BaseModel
    from app.models.organization import Organization
    from app.models.site import Site, SiteType
    from app.models.station import Station, StationType
    from app.models.user import User, UserRole
    from app.models.audit_log import AuditLog, AuditAction, AuditActorType
    from app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )
except ImportError:
    from backend.app.db.base import Base, BaseModel
    from backend.app.models.organization import Organization
    from backend.app.models.site import Site, SiteType
    from backend.app.models.station import Station, StationType
    from backend.app.models.user import User, UserRole
    from backend.app.models.audit_log import AuditLog, AuditAction, AuditActorType
    from backend.app.db.session import (
        sync_engine,
        get_async_session,
        get_sync_session
    )


@pytest.fixture(scope="module", autouse=True)
def setup_audit_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def test_audit_log_inheritance_and_fields():
    assert issubclass(AuditLog, BaseModel)
    assert "audit_logs" in Base.metadata.tables
    table = Base.metadata.tables["audit_logs"]

    # Verify fields
    assert "id" in table.columns
    assert "organization_id" in table.columns
    assert "site_id" in table.columns
    assert "station_id" in table.columns
    assert "actor_user_id" in table.columns
    assert "actor_type" in table.columns
    assert "action" in table.columns
    assert "resource_type" in table.columns
    assert "resource_id" in table.columns
    assert "action_description" in table.columns
    assert "audit_metadata" in table.columns
    assert "ip_address" in table.columns
    assert "user_agent" in table.columns
    assert "occurred_at" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns

    # Verify FKs and SET NULL
    for col_name in ["organization_id", "site_id", "station_id", "actor_user_id"]:
        col = table.columns[col_name]
        assert len(col.foreign_keys) == 1
        fk = list(col.foreign_keys)[0]
        assert fk.ondelete == "SET NULL"
        assert col.index is True
        assert col.nullable is True


def _create_hierarchy(session):
    suffix = uuid.uuid4().hex[:6]
    org = Organization(name=f"Org {suffix}", organization_code=f"ORG-{suffix}")
    session.add(org)
    session.flush()

    user = User(organization_id=org.id, name=f"User {suffix}", email=f"user-{suffix}@example.com", password_hash="dummy")
    session.add(user)

    site = Site(organization_id=org.id, name=f"Site {suffix}", site_code=f"SITE-{suffix}", site_type=SiteType.OTHER)
    session.add(site)
    session.flush()

    stn = Station(site_id=site.id, name=f"Stn {suffix}", station_code=f"STN-{suffix}", station_type=StationType.OTHER)
    session.add(stn)
    session.flush()

    return org, user, site, stn


def test_audit_log_creation_and_defaults():
    with get_sync_session() as session:
        org, user, site, stn = _create_hierarchy(session)

        log = AuditLog(
            organization_id=org.id,
            site_id=site.id,
            station_id=stn.id,
            actor_user_id=user.id,
            action=AuditAction.UPDATE,
            resource_type="STATION_SETTINGS",
            resource_id=stn.id,
            action_description="Updated threshold",
            audit_metadata={"changed": True},
            ip_address="192.168.1.1",
            user_agent="pytest"
        )
        session.add(log)
        session.flush()

        log_id = log.id

    with get_sync_session() as session:
        log = session.get(AuditLog, log_id)
        assert log.actor_type == AuditActorType.USER
        assert log.action == AuditAction.UPDATE
        assert log.resource_type == "STATION_SETTINGS"
        assert log.resource_id == stn.id
        assert log.action_description == "Updated threshold"
        assert log.audit_metadata == {"changed": True}
        assert log.occurred_at is not None
        assert log.created_at is not None


def test_audit_log_nullables_allowed():
    with get_sync_session() as session:
        log = AuditLog(
            action=AuditAction.OTHER,
            actor_type=AuditActorType.SYSTEM,
            action_description="System startup",
            resource_type="SYSTEM"
        )
        session.add(log)
        session.flush()
        assert log.id is not None
        assert log.organization_id is None
        assert log.site_id is None


def test_audit_log_missing_required():
    with pytest.raises(IntegrityError):
        with get_sync_session() as session:
            log = AuditLog(
                actor_type=AuditActorType.USER,
                resource_type="TEST",
                action_description="desc"
            )
            session.add(log)
            session.flush()


def test_audit_log_deletion_survival_set_null():
    with get_sync_session() as session:
        org, user, site, stn = _create_hierarchy(session)
        log = AuditLog(
            organization_id=org.id,
            site_id=site.id,
            station_id=stn.id,
            actor_user_id=user.id,
            action=AuditAction.DELETE,
            resource_type="TEST",
            action_description="test"
        )
        session.add(log)
        session.flush()
        log_id = log.id
        stn_id = stn.id
        org_id = org.id

    # Delete station
    with get_sync_session() as session:
        stn = session.get(Station, stn_id)
        session.delete(stn)
        session.commit()

    with get_sync_session() as session:
        log = session.get(AuditLog, log_id)
        assert log is not None
        assert log.station_id is None
        assert log.organization_id == org_id




def test_audit_log_relationships():
    with get_sync_session() as session:
        org, user, site, stn = _create_hierarchy(session)
        log = AuditLog(
            organization_id=org.id,
            actor_user_id=user.id,
            action=AuditAction.LOGIN,
            resource_type="USER",
            action_description="login"
        )
        session.add(log)
        session.flush()
        
        assert log.organization.id == org.id
        assert log.actor_user.id == user.id
        assert log in org.audit_logs
        assert log in user.audit_logs


def test_multiple_audit_records_same_resource():
    with get_sync_session() as session:
        org, user, site, stn = _create_hierarchy(session)
        res_id = uuid.uuid4()
        
        log1 = AuditLog(action=AuditAction.CREATE, resource_type="STATION", resource_id=res_id, action_description="c")
        log2 = AuditLog(action=AuditAction.UPDATE, resource_type="STATION", resource_id=res_id, action_description="u")
        
        session.add_all([log1, log2])
        session.flush()
        
        assert log1.id is not None
        assert log2.id is not None


@pytest.mark.asyncio
async def test_audit_log_async_crud():
    async with get_async_session() as session:
        log = AuditLog(
            action=AuditAction.CONFIGURE,
            resource_type="NETWORK",
            action_description="reconfigure"
        )
        session.add(log)
        await session.flush()
        log_id = log.id

    async with get_async_session() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.id == log_id))
        queried = result.scalar_one()
        assert queried.action == AuditAction.CONFIGURE
