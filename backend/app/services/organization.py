import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site
from app.schemas.organization import OrganizationCreate, OrganizationUpdate

class OrganizationAlreadyExistsException(Exception):
    pass

class OrganizationNotFoundException(Exception):
    pass

class OrganizationHasDependentSitesException(Exception):
    pass


async def create_organization(session: AsyncSession, req: OrganizationCreate) -> Organization:
    code = req.organization_code.strip().upper()
    name = req.name.strip()
    
    # Check for existing code
    stmt = select(Organization).where(Organization.organization_code == code)
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise OrganizationAlreadyExistsException(f"Organization code '{code}' already exists.")
        
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        organization_code=code,
        status=req.status or OrganizationStatus.ACTIVE
    )
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def get_organization(session: AsyncSession, org_id: uuid.UUID) -> Optional[Organization]:
    stmt = select(Organization).where(Organization.id == org_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_organizations(session: AsyncSession) -> Sequence[Organization]:
    stmt = select(Organization).order_by(Organization.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def update_organization(
    session: AsyncSession,
    org: Organization,
    req: OrganizationUpdate
) -> Organization:
    if req.organization_code is not None:
        new_code = req.organization_code.strip().upper()
        if new_code != org.organization_code:
            stmt = select(Organization).where(Organization.organization_code == new_code)
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise OrganizationAlreadyExistsException(f"Organization code '{new_code}' already exists.")
            org.organization_code = new_code
            
    if req.name is not None:
        org.name = req.name.strip()
        
    if req.status is not None:
        org.status = req.status
        
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def delete_organization(session: AsyncSession, org: Organization) -> None:
    # Check if dependent sites exist
    stmt = select(func.count(Site.id)).where(Site.organization_id == org.id)
    res = await session.execute(stmt)
    count = res.scalar() or 0
    if count > 0:
        raise OrganizationHasDependentSitesException("Cannot delete organization with active sites.")
        
    await session.delete(org)
    await session.commit()
