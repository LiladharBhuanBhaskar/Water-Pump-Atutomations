import sys
import os
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

try:
    from app.core.config import settings
    from app.api.v1.health import router as health_router
    from app.api.v1.auth import router as auth_router
    from app.api.v1.organizations import router as organizations_router
    from app.api.v1.sites import router as sites_router
    from app.api.v1.stations import router as stations_router
    from app.api.v1.controllers import router as controllers_router
    from app.api.v1.motors import router as motors_router
    from app.api.v1.sensors import router as sensors_router
    from app.api.v1.devices import router as devices_router
    from app.api.v1.motor_control import router as motor_control_router
    from app.api.v1.automation_rules import router as automation_rules_router
    from app.api.v1.schedules import router as schedules_router
    from app.api.v1.events import router as events_router
    from app.api.v1.audit_logs import router as audit_logs_router
    from app.api.v1.notifications import router as notifications_router
    from app.api.v1.fleet import router as fleet_router
    from app.api.v1.users import router as users_router
    from app.api.v1.websocket import router as ws_router
except ImportError:
    from backend.app.core.config import settings
    from backend.app.api.v1.health import router as health_router
    from backend.app.api.v1.auth import router as auth_router
    from backend.app.api.v1.users import router as users_router
    from backend.app.api.v1.organizations import router as organizations_router
    from backend.app.api.v1.sites import router as sites_router
    from backend.app.api.v1.stations import router as stations_router
    from backend.app.api.v1.controllers import router as controllers_router
    from backend.app.api.v1.motors import router as motors_router
    from backend.app.api.v1.sensors import router as sensors_router
    from backend.app.api.v1.devices import router as devices_router
    from backend.app.api.v1.motor_control import router as motor_control_router
    from backend.app.api.v1.automation_rules import router as automation_rules_router
    from backend.app.api.v1.schedules import router as schedules_router
    from backend.app.api.v1.events import router as events_router
    from backend.app.api.v1.audit_logs import router as audit_logs_router
    from backend.app.api.v1.notifications import router as notifications_router
    from backend.app.api.v1.fleet import router as fleet_router
    from backend.app.api.v1.websocket import router as ws_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("hydracontrol")


def get_database_identity():
    import os, sqlite3
    pid = os.getpid()
    cwd = os.getcwd()
    db_url = settings.DATABASE_URL
    clean_path = db_url.split(":///")[-1] if ":///" in db_url else db_url
    exists = os.path.exists(clean_path)
    file_size = os.path.getsize(clean_path) if exists else 0
    table_count = 0
    users_exists = False
    user_count = 0
    alembic_rev = "N/A"
    if exists:
        try:
            conn = sqlite3.connect(clean_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            table_count = len(tables)
            users_exists = "users" in tables
            if users_exists:
                cur.execute("SELECT COUNT(*) FROM users;")
                user_count = cur.fetchone()[0]
            if "alembic_version" in tables:
                cur.execute("SELECT version_num FROM alembic_version;")
                row = cur.fetchone()
                if row:
                    alembic_rev = row[0]
            conn.close()
        except Exception:
            pass
    return {
        "pid": pid,
        "cwd": cwd,
        "database_url": db_url,
        "resolved_path": clean_path,
        "realpath": os.path.realpath(clean_path) if exists else "N/A",
        "exists": exists,
        "file_size": file_size,
        "table_count": table_count,
        "users_table_exists": users_exists,
        "user_count": user_count,
        "alembic_revision": alembic_rev
    }


def print_database_identity():
    ident = get_database_identity()
    print("==================================================")
    print("HYDRACONTROL DATABASE IDENTITY")
    print("==================================================")
    print(f"PID: {ident['pid']}")
    print(f"PROCESS CWD: {ident['cwd']}")
    print(f"DATABASE_URL: {ident['database_url']}")
    print(f"RESOLVED DATABASE PATH: {ident['resolved_path']}")
    print(f"DATABASE REALPATH: {ident['realpath']}")
    print(f"DATABASE EXISTS: {ident['exists']}")
    print(f"DATABASE FILE SIZE: {ident['file_size']} bytes")
    print(f"DATABASE TABLE COUNT: {ident['table_count']}")
    print(f"USERS TABLE EXISTS: {ident['users_table_exists']}")
    print(f"USER COUNT: {ident['user_count']}")
    print(f"ALEMBIC REVISION: {ident['alembic_revision']}")
    print("==================================================")


import asyncio
from app.db.session import AsyncSessionLocal
from app.services.timer_scheduler_service import timer_scheduler


async def _scheduler_background_loop():
    logger.info("Starting background Timer & Schedule evaluator loop...")
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await timer_scheduler.check_and_execute_schedules(session)
                await timer_scheduler.check_and_process_motor_timers(session)
                await session.commit()
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in scheduler background loop: {e}", exc_info=False)
        await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print_database_identity()
    logger.info(f"Starting {settings.PROJECT_NAME} in {settings.ENVIRONMENT} mode...")
    scheduler_task = asyncio.create_task(_scheduler_background_loop())
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info(f"Shutting down {settings.PROJECT_NAME}...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

from app.core.security_headers import SecurityHeadersMiddleware
from app.core.logging_middleware import CorrelationAndLoggingMiddleware

# Security Headers & Correlation Logging Middleware (Phase 23 & 24)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationAndLoggingMiddleware)

# CORS Middleware (Permits Web, Mobile APK, Capacitor & Local LAN IPs)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(https?://.*|capacitor://localhost)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth")
app.include_router(organizations_router, prefix=f"{settings.API_V1_STR}/organizations")
app.include_router(sites_router, prefix=f"{settings.API_V1_STR}/sites")
app.include_router(stations_router, prefix=f"{settings.API_V1_STR}/stations")
app.include_router(controllers_router, prefix=f"{settings.API_V1_STR}/controllers")
app.include_router(motors_router, prefix=f"{settings.API_V1_STR}/motors")
app.include_router(motor_control_router, prefix=f"{settings.API_V1_STR}/motors")
app.include_router(sensors_router, prefix=f"{settings.API_V1_STR}/sensors")
app.include_router(automation_rules_router, prefix=f"{settings.API_V1_STR}/automation-rules")
app.include_router(schedules_router, prefix=settings.API_V1_STR)
app.include_router(events_router, prefix=settings.API_V1_STR)
app.include_router(audit_logs_router, prefix=settings.API_V1_STR)
app.include_router(notifications_router, prefix=settings.API_V1_STR)
app.include_router(fleet_router, prefix=settings.API_V1_STR)
app.include_router(devices_router, prefix=f"{settings.API_V1_STR}/devices")
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users")
app.include_router(ws_router, prefix=settings.API_V1_STR)



@app.get("/", tags=["Root"])
async def root():
    return {
        "app": settings.PROJECT_NAME,
        "docs": f"{settings.API_V1_STR}/docs",
        "health": "/health",
        "version": "0.1.0-alpha"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
