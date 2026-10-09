import pytest
import subprocess
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.organization import Organization
from app.models.user import User
from app.models.site import Site
from app.models.station import Station
from app.models.controller import Controller
from app.models.motor import Motor
from app.models.sensor import Sensor
from app.models.settings import StationSettings
from app.models.automation_rule import AutomationRule
from app.models.telemetry import TelemetryReading
from app.models.motor_event import MotorEvent
from app.models.motor_command import MotorCommand

from app.db.session import get_async_session, sync_engine
from app.db.base import Base

@pytest.fixture(scope="module", autouse=True)
def setup_test_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.mark.asyncio
async def test_seed_demo_script():
    # Set ENVIRONMENT to development to allow seed
    os.environ["ENVIRONMENT"] = "development"
    
    # Run the seed script via subprocess to test the actual CLI behavior
    # Use the current python interpreter
    import sys
    
    # We must run it using the current database. However, the subprocess will use its own session.
    # To test the side-effects in the SAME test DB, we can either call the async function directly
    # or ensure the subprocess targets the test DB.
    # We'll just import and call it directly here.
    
    from scripts.seed_demo import seed_demo_data
    
    async with get_async_session() as db_session:
        # Run once
        await seed_demo_data(session=db_session)
        
        # Verify counts
        orgs = (await db_session.execute(select(Organization))).scalars().all()
        assert len(orgs) == 1
        
        users = (await db_session.execute(select(User))).scalars().all()
        assert len(users) == 5
        
        sites = (await db_session.execute(select(Site))).scalars().all()
        assert len(sites) == 1
        
        stations = (await db_session.execute(select(Station))).scalars().all()
        assert len(stations) == 1
        
        controllers = (await db_session.execute(select(Controller))).scalars().all()
        assert len(controllers) == 1
        
        motors = (await db_session.execute(select(Motor))).scalars().all()
        assert len(motors) == 2
        
        sensors = (await db_session.execute(select(Sensor))).scalars().all()
        assert len(sensors) == 5
        
        settings = (await db_session.execute(select(StationSettings))).scalars().all()
        assert len(settings) == 1
        
        rules = (await db_session.execute(select(AutomationRule))).scalars().all()
        assert len(rules) == 3
        
        telemetry = (await db_session.execute(select(TelemetryReading))).scalars().all()
        assert len(telemetry) == 5
        
        events = (await db_session.execute(select(MotorEvent))).scalars().all()
        assert len(events) == 8
        
        cmds = (await db_session.execute(select(MotorCommand))).scalars().all()
        assert len(cmds) == 0
        
        # Run again - Idempotency
        await seed_demo_data(session=db_session)
        
        orgs2 = (await db_session.execute(select(Organization))).scalars().all()
        assert len(orgs2) == 1
