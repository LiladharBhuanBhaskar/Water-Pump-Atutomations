import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_

from app.models.station import Station, StationStatus, StationType
from app.models.site import Site
from app.models.controller import Controller
from app.schemas.station import StationCreate, StationUpdate

class StationAlreadyExistsException(Exception):
    pass

class StationNotFoundException(Exception):
    pass

class StationHasDependentControllersException(Exception):
    pass


async def create_station(
    session: AsyncSession,
    req: StationCreate,
    target_site_id: uuid.UUID
) -> Station:
    code = req.station_code.strip().upper()
    name = req.name.strip()

    # Check composite uniqueness on (site_id, station_code)
    stmt = select(Station).where(
        and_(
            Station.site_id == target_site_id,
            Station.station_code == code
        )
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none() is not None:
        raise StationAlreadyExistsException(f"Station code '{code}' already exists in this site.")

    station = Station(
        id=uuid.uuid4(),
        site_id=target_site_id,
        name=name,
        station_code=code,
        station_type=req.station_type or StationType.HOME_PUMP,
        location=req.location.strip() if req.location else None,
        timezone=req.timezone or "Asia/Kolkata",
        description=req.description.strip() if req.description else None,
        status=req.status or StationStatus.ACTIVE
    )
    session.add(station)
    await session.commit()
    await session.refresh(station)
    return station


async def get_station_by_id(session: AsyncSession, station_id: uuid.UUID) -> Optional[Station]:
    stmt = select(Station).where(Station.id == station_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_stations_for_org_or_site(
    session: AsyncSession,
    organization_id: Optional[uuid.UUID] = None,
    site_id: Optional[uuid.UUID] = None
) -> Sequence[Station]:
    stmt = select(Station).join(Site, Station.site_id == Site.id)
    
    if organization_id is not None:
        stmt = stmt.where(Site.organization_id == organization_id)
    if site_id is not None:
        stmt = stmt.where(Station.site_id == site_id)

    stmt = stmt.order_by(Station.created_at.desc())
    res = await session.execute(stmt)
    return res.scalars().all()


async def update_station(
    session: AsyncSession,
    station: Station,
    req: StationUpdate
) -> Station:
    if req.station_code is not None:
        new_code = req.station_code.strip().upper()
        if new_code != station.station_code:
            stmt = select(Station).where(
                and_(
                    Station.site_id == station.site_id,
                    Station.station_code == new_code
                )
            )
            res = await session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                raise StationAlreadyExistsException(f"Station code '{new_code}' already exists in this site.")
            station.station_code = new_code

    if req.name is not None:
        station.name = req.name.strip()

    if req.station_type is not None:
        station.station_type = req.station_type

    if req.location is not None:
        station.location = req.location.strip() if req.location else None

    if req.timezone is not None:
        station.timezone = req.timezone.strip()

    if req.description is not None:
        station.description = req.description.strip() if req.description else None

    if req.status is not None:
        station.status = req.status

    session.add(station)
    await session.commit()
    await session.refresh(station)
    return station


async def delete_station(session: AsyncSession, station: Station) -> None:
    # Check if dependent controllers exist
    stmt = select(func.count(Controller.id)).where(Controller.station_id == station.id)
    res = await session.execute(stmt)
    count = res.scalar() or 0
    if count > 0:
        raise StationHasDependentControllersException("Cannot delete station with active controllers.")

    await session.delete(station)
    await session.commit()
