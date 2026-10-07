import asyncio
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from passlib.context import CryptContext

from app.db.session import AsyncSessionLocal, create_async_engine
from app.core.config import settings
from app.models.organization import Organization, OrganizationStatus
from app.models.user import User, UserRole
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.sensor import Sensor, SensorStatus, SensorType
from app.models.settings import StationSettings
from app.models.automation_rule import AutomationRule, AutomationRuleType, AutomationRuleStatus, AutomationOperator, AutomationAction
from app.models.telemetry import TelemetryReading
from app.models.motor_event import MotorEvent, MotorEventType, MotorEventSource
from app.models.motor_command import MotorCommand, CommandType, CommandStatus

from app.core.security import get_password_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("seed")

async def get_or_create(session, model, defaults=None, **kwargs):
    query = select(model).filter_by(**kwargs)
    result = await session.execute(query)
    instance = result.scalars().first()
    
    if instance:
        return instance, False
    
    params = dict((k, v) for k, v in kwargs.items())
    if defaults:
        params.update(defaults)
        
    instance = model(**params)
    session.add(instance)
    return instance, True

async def seed_demo_data(session: AsyncSession = None):
    if settings.ENVIRONMENT.lower() != "development" and "--force" not in sys.argv:
        logger.error("SEED ABORTED: Not in 'development' environment.")
        logger.error("Set ENVIRONMENT=development or use --force to override.")
        sys.exit(1)
        
    password = os.environ.get("HYDRACONTROL_DEMO_PASSWORD", "SecretPass123!")
    hashed_password = get_password_hash(password)
    
    if session is not None:
        await _run_seed(session, hashed_password)
    else:
        async with AsyncSessionLocal() as new_session:
            await _run_seed(new_session, hashed_password)

async def _run_seed(session: AsyncSession, hashed_password: str):
        try:
            # 1. Organization
            org, _ = await get_or_create(
                session, Organization,
                organization_code="DEMO-ORG-001",
                defaults={"name": "HydraControl Demo Organization", "status": OrganizationStatus.ACTIVE}
            )
            await session.flush()
            
            # 2. Users
            users_data = [
                ("Demo Super Admin", "admin@hydracontrol.io", UserRole.SUPER_ADMIN),
                ("Demo Organization Admin", "orgadmin@hydracontrol.io", UserRole.ORGANIZATION_ADMIN),
                ("Demo Site Manager", "manager@hydracontrol.io", UserRole.SITE_MANAGER),
                ("Demo Station Operator", "operator@hydracontrol.io", UserRole.STATION_OPERATOR),
                ("Demo Viewer", "viewer@hydracontrol.io", UserRole.VIEWER),
            ]
            
            users = {}
            for name, email, role in users_data:
                u, _ = await get_or_create(
                    session, User, email=email,
                    defaults={
                        "name": name,
                        "password_hash": hashed_password,
                        "role": role,
                        "is_active": True,
                        "organization_id": org.id
                    }
                )
                users[role] = u
            await session.flush()
            
            # 3. Site
            site, _ = await get_or_create(
                session, Site,
                organization_id=org.id,
                site_code="DEMO-SITE-001",
                defaults={
                    "name": "Demo Main Site",
                    "site_type": SiteType.BUILDING,
                    "location": "Jaipur Demo Location",
                    "timezone": "Asia/Kolkata",
                    "status": SiteStatus.ACTIVE
                }
            )
            await session.flush()
            
            # 4. Station
            station, _ = await get_or_create(
                session, Station,
                site_id=site.id,
                station_code="DEMO-STN-001",
                defaults={
                    "name": "Demo Water Pump Station",
                    "station_type": StationType.WATER_SUPPLY,
                    "location": "Demo Main Site",
                    "timezone": "Asia/Kolkata",
                    "description": "Development/demo water pump station",
                    "status": StationStatus.ACTIVE
                }
            )
            await session.flush()
            
            # 5. Controller
            controller, _ = await get_or_create(
                session, Controller,
                station_id=station.id,
                controller_code="DEMO-CTRL-001",
                defaults={
                    "name": "Demo ESP32 Controller",
                    "device_uid": "DEMO-ESP32-001",
                    "controller_type": ControllerType.ESP32,
                    "status": ControllerStatus.ACTIVE,
                    "firmware_version": "1.0.0-demo",
                    "description": "Development/demo ESP32 controller"
                }
            )
            await session.flush()
            
            # 6. Motors
            motor1, _ = await get_or_create(
                session, Motor,
                controller_id=controller.id,
                motor_code="DEMO-MOTOR-001",
                defaults={
                    "name": "Demo Main Pump",
                    "motor_type": MotorType.WATER_PUMP,
                    "status": MotorStatus.OFF,
                    "rated_power": 1.50,
                    "description": "Development/demo primary water pump"
                }
            )
            motor2, _ = await get_or_create(
                session, Motor,
                controller_id=controller.id,
                motor_code="DEMO-MOTOR-002",
                defaults={
                    "name": "Demo Backup Pump",
                    "motor_type": MotorType.BOOSTER_PUMP,
                    "status": MotorStatus.OFF,
                    "rated_power": 1.00,
                    "description": "Development/demo backup water pump"
                }
            )
            await session.flush()
            
            # 7. Sensors
            s_level, _ = await get_or_create(
                session, Sensor,
                controller_id=controller.id,
                sensor_code="DEMO-SENSOR-LEVEL-001",
                defaults={
                    "name": "Demo Tank Level Sensor",
                    "sensor_type": SensorType.WATER_LEVEL,
                    "status": SensorStatus.ACTIVE
                }
            )
            s_turb, _ = await get_or_create(
                session, Sensor,
                controller_id=controller.id,
                sensor_code="DEMO-SENSOR-TURBIDITY-001",
                defaults={
                    "name": "Demo Turbidity Sensor",
                    "sensor_type": SensorType.TURBIDITY,
                    "status": SensorStatus.ACTIVE
                }
            )
            s_flow, _ = await get_or_create(
                session, Sensor,
                controller_id=controller.id,
                sensor_code="DEMO-SENSOR-FLOW-001",
                defaults={
                    "name": "Demo Flow Sensor",
                    "sensor_type": SensorType.FLOW,
                    "status": SensorStatus.ACTIVE
                }
            )
            await session.flush()
            
            # 8. StationSettings
            settings_obj, _ = await get_or_create(
                session, StationSettings,
                station_id=station.id,
                defaults={
                    "timezone": "Asia/Kolkata",
                    "auto_stop_on_tank_full": True,
                    "water_level_threshold": 95.0,
                    "turbidity_threshold": 5.0,
                    "default_timer_seconds": 1800,
                    "offline_alert_enabled": True,
                    "offline_timeout_seconds": 300
                }
            )
            await session.flush()
            
            # 9. AutomationRules
            r1, _ = await get_or_create(
                session, AutomationRule,
                station_id=station.id,
                name="Demo Tank Full Stop",
                defaults={
                    "description": "Stop primary pump when tank level reaches configured limit",
                    "rule_type": AutomationRuleType.WATER_LEVEL,
                    "sensor_id": s_level.id,
                    "operator": AutomationOperator.GREATER_THAN_OR_EQUAL,
                    "threshold_value": 95.0,
                    "threshold_unit": "percent",
                    "motor_id": motor1.id,
                    "action": AutomationAction.STOP_MOTOR,
                    "status": AutomationRuleStatus.ACTIVE,
                    "created_by": users[UserRole.ORGANIZATION_ADMIN].id
                }
            )
            r2, _ = await get_or_create(
                session, AutomationRule,
                station_id=station.id,
                name="Demo Turbidity Protection",
                defaults={
                    "description": "Stop primary pump when turbidity exceeds configured limit",
                    "rule_type": AutomationRuleType.TURBIDITY,
                    "sensor_id": s_turb.id,
                    "operator": AutomationOperator.GREATER_THAN,
                    "threshold_value": 5.0,
                    "threshold_unit": "NTU",
                    "motor_id": motor1.id,
                    "action": AutomationAction.STOP_MOTOR,
                    "status": AutomationRuleStatus.ACTIVE,
                    "created_by": users[UserRole.ORGANIZATION_ADMIN].id
                }
            )
            r3, _ = await get_or_create(
                session, AutomationRule,
                station_id=station.id,
                name="Demo Pump Timer",
                defaults={
                    "description": "Development timer rule",
                    "rule_type": AutomationRuleType.TIMER,
                    "duration_seconds": 1800,
                    "motor_id": motor1.id,
                    "action": AutomationAction.STOP_MOTOR,
                    "status": AutomationRuleStatus.ACTIVE,
                    "created_by": users[UserRole.ORGANIZATION_ADMIN].id
                }
            )
            await session.flush()
            
            # 10. Telemetry & Events (Deterministic timestamp)
            base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            
            # Check if telemetry exists for this sensor and base_time to avoid duplicates
            t_check = await session.execute(select(TelemetryReading).filter_by(sensor_id=s_level.id, occurred_at=base_time))
            if not t_check.scalars().first():
                import uuid
                level_vals = [70.0, 80.0, 90.0, 95.0]
                for i, val in enumerate(level_vals):
                    session.add(TelemetryReading(id=uuid.uuid4(), sensor_id=s_level.id, value=val, unit="percent", occurred_at=base_time + timedelta(minutes=i*10)))
                
                turb_vals = [2.0, 3.0, 4.0, 6.0]
                for i, val in enumerate(turb_vals):
                    session.add(TelemetryReading(id=uuid.uuid4(), sensor_id=s_turb.id, value=val, unit="NTU", occurred_at=base_time + timedelta(minutes=i*10)))
                
                flow_vals = [10.0, 12.0, 11.5, 9.5]
                for i, val in enumerate(flow_vals):
                    session.add(TelemetryReading(id=uuid.uuid4(), sensor_id=s_flow.id, value=val, unit="L/min", occurred_at=base_time + timedelta(minutes=i*10)))
                    
                # Motor Events
                event_types = [MotorEventType.STARTED, MotorEventType.STOPPED, MotorEventType.STARTED, MotorEventType.STOPPED]
                for i, ev_type in enumerate(event_types):
                    session.add(MotorEvent(id=uuid.uuid4(), motor_id=motor1.id, event_type=ev_type, source=MotorEventSource.SYSTEM, occurred_at=base_time + timedelta(minutes=i*10)))
                    
                # Motor Commands
                cmd_types = [CommandType.START, CommandType.STOP]
                for i, cmd_type in enumerate(cmd_types):
                    session.add(MotorCommand(id=uuid.uuid4(), motor_id=motor1.id, command_type=cmd_type, requested_by=users[UserRole.STATION_OPERATOR].id, status=CommandStatus.EXECUTED, requested_at=base_time + timedelta(minutes=i*20)))
                    
            await session.commit()
            
            print("HydraControl demo seed")
            print("----------------------\n")
            print(f"Environment: {settings.ENVIRONMENT}")
            print(f"Organization: created/existing")
            print(f"Users: 5")
            print(f"Site: created/existing")
            print(f"Station: created/existing")
            print(f"Controller: created/existing")
            print(f"Motors: 2")
            print(f"Sensors: 3")
            print(f"Settings: created/existing")
            print(f"Automation rules: 3")
            
            # Count telemetry and events
            t_count = (await session.execute(select(TelemetryReading))).scalars().all()
            e_count = (await session.execute(select(MotorEvent))).scalars().all()
            c_count = (await session.execute(select(MotorCommand))).scalars().all()
            
            print(f"Telemetry readings: {len(t_count)}")
            print(f"Motor events: {len(e_count)}")
            print(f"Motor commands: {len(c_count)}\n")
            print("Seed completed successfully.")

        except Exception as e:
            await session.rollback()
            logger.error(f"Seed failed: {e}")
            raise e

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
