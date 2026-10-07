import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station
from app.schemas.site import SiteCreate, SiteUpdate

class SiteAlreadyExistsException(Exception):
    pass

class SiteNotFoundException(Exception):
    pass

class SiteHasDependentStationsException(Exception):
    pass


async def create_site(
    session: AsyncSession,
    req: SiteCreate,
    target_org_id: uuid.UUID
) -> Site:
    code = req.site_code.strip().upper()
    name = req.name.strip()

    # Check composite uniqueness on (organization_id, site_code)
    stmt = select(Site).where(
        and_(
            Site.organization_id == target_org_id,
            Site.site_code == code
        )
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise SiteAlreadyExistsException(f"Site code '{code}' already exists in this organization.")

    site = Site(
        id=uuid.uuid4(),
        organization_id=target_org_id,
        name=name,
        site_code=code,
        site_type=req.site_type or SiteType.HOME,
        location=req.location.strip() if req.location else None,
        timezone=req.timezone or "Asia/Kolkata",
        status=req.status or SiteStatus.ACTIVE
    )
    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def get_site_by_id(session: AsyncSession, site_id: uuid.UUID) -> Optional[Site]:
    stmt = select(Site).where(Site.id == site_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_sites_for_org(
    session: AsyncSession,
    organization_id: Optional[uuid.UUID] = None
) -> Sequence[Site]:
    stmt = select(Site)
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    stmt = stmt.order_by(Site.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def update_site(
    session: AsyncSession,
    site: Site,
    req: SiteUpdate
) -> Site:
    if req.site_code is not None:
        new_code = req.site_code.strip().upper()
        if new_code != site.site_code:
            stmt = select(Site).where(
                and_(
                    Site.organization_id == site.organization_id,
                    Site.site_code == new_code
                )
            )
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise SiteAlreadyExistsException(f"Site code '{new_code}' already exists in this organization.")
            site.site_code = new_code

    if req.name is not None:
        site.name = req.name.strip()

    if req.site_type is not None:
        site.site_type = req.site_type

    if req.location is not None:
        site.location = req.location.strip() if req.location else None

    if req.timezone is not None:
        site.timezone = req.timezone.strip()

    if req.status is not None:
        site.status = req.status

    session.add(site)
    await session.commit()
    await session.refresh(site)
    return site


async def delete_site(session: AsyncSession, site: Site) -> None:
    # Check if dependent stations exist
    stmt = select(func.count(Station.id)).where(Station.site_id == site.id)
    res = await session.execute(stmt)
    count = res.scalar() or 0
    if count > 0:
        raise SiteHasDependentStationsException("Cannot delete site with active stations.")

    await session.delete(site)
    await session.commit()
