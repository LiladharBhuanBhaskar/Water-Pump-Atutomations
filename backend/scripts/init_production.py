"""
HydraControl — Production Database Bootstrap & Initial Provisioning Script
Creates all database tables, verifies connections, and ensures a default Super Admin account exists.
Safe to run multiple times (idempotent).
"""

import sys
import os
import asyncio
import uuid
import logging

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base
from app.db.session import async_engine, AsyncSessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User, UserRole
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.settings import StationSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("hydracontrol.init")


async def init_production_db():
    logger.info("Initializing database schema...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✓ Database tables verified.")

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@hydracontrol.io")
    admin_password = os.environ.get("ADMIN_PASSWORD", "SecretPass123!")

    async with AsyncSessionLocal() as session:
        # Check if any user exists
        user_check = await session.execute(select(User).limit(1))
        existing_user = user_check.scalar_one_or_none()

        if existing_user is None:
            logger.info("No existing users found. Creating default Commercial Organization and Super Admin...")
            
            # 1. Organization
            org = Organization(
                id=uuid.uuid4(),
                name="HydraControl Commercial Enterprise",
                organization_code="ORG-HYDRA-PRIMARY",
                status=OrganizationStatus.ACTIVE,
            )
            session.add(org)
            await session.flush()

            # 2. Super Admin User
            admin = User(
                id=uuid.uuid4(),
                organization_id=org.id,
                email=admin_email,
                name="System Administrator",
                role=UserRole.SUPER_ADMIN,
                password_hash=get_password_hash(admin_password),
                is_active=True,
            )
            session.add(admin)

            # 3. Default Site
            site = Site(
                id=uuid.uuid4(),
                organization_id=org.id,
                name="Main Water Facility",
                site_code="SITE-HQ-01",
                site_type=SiteType.COMMERCIAL,
                timezone="Asia/Kolkata",
                status=SiteStatus.ACTIVE,
            )
            session.add(site)
            await session.flush()

            # 4. Default Station
            station = Station(
                id=uuid.uuid4(),
                site_id=site.id,
                name="Overhead Tank Station #1",
                station_code="STN-TNK-01",
                station_type=StationType.WATER_SUPPLY,
                timezone="Asia/Kolkata",
                status=StationStatus.ACTIVE,
            )
            session.add(station)
            await session.flush()

            # 5. Station Operational Settings
            st_settings = StationSettings(
                id=uuid.uuid4(),
                station_id=station.id,
                timezone="Asia/Kolkata",
                auto_stop_on_tank_full=True,
                water_level_threshold=95.0,
                turbidity_threshold=25.0,
                default_timer_seconds=1800,
                offline_alert_enabled=True,
                offline_timeout_seconds=60,
            )
            session.add(st_settings)

            # 6. Default Controller
            controller = Controller(
                id=uuid.uuid4(),
                station_id=station.id,
                name="ESP32 Gateway Alpha",
                controller_code="CTRL-ESP-01",
                device_uid="HYDRA-PROD-ESP32-001",
                controller_type=ControllerType.ESP32,
                status=ControllerStatus.ONLINE,
                firmware_version="1.0.0-prod",
            )
            session.add(controller)
            await session.flush()

            # 7. Default Pump Motor
            motor = Motor(
                id=uuid.uuid4(),
                controller_id=controller.id,
                name="Main Submersible Motor",
                motor_code="PUMP-SUB-01",
                motor_type=MotorType.SUBMERSIBLE_PUMP,
                status=MotorStatus.OFF,
                rated_power_kw=7.5,
                rated_voltage=415,
                rated_current_amps=14.2,
            )
            session.add(motor)

            await session.commit()
            logger.info("==================================================")
            logger.info("✓ PRODUCTION BOOTSTRAP COMPLETE!")
            logger.info(f"Default Admin: {admin_email}")
            logger.info(f"Default Password: {admin_password}")
            logger.info("==================================================")
        else:
            logger.info(f"Database already provisioned (found user: {existing_user.email}).")


if __name__ == "__main__":
    asyncio.run(init_production_db())
