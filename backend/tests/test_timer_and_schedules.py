"""
HydraControl — Unit & Integration Tests for Timers & Schedules (Phase 16 - Wave A).
Verifies deterministic countdown evaluation, 1-min pre-expiration warnings, auto-stop command dispatches,
schedule CRUD APIs, RBAC restrictions, and tenant isolation.
"""

import uuid
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.db.base import Base
from app.db.session import sync_engine, get_sync_session, AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.site import Site, SiteStatus, SiteType
from app.models.station import Station, StationStatus, StationType
from app.models.controller import Controller, ControllerStatus, ControllerType
from app.models.motor import Motor, MotorStatus, MotorType
from app.models.settings import StationSettings
from app.models.automation_rule import AutomationRule, AutomationRuleType, AutomationRuleStatus, AutomationAction
from app.core.security import create_access_token, get_password_hash
from app.services.timer_scheduler_service import timer_scheduler, TimerSchedulerService
from app.services.schedule_service import list_schedules_for_station, create_schedule, update_schedule, delete_schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def helper_create_test_hierarchy():
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="Timer Org",
            organization_code=f"TMR-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)
        session.flush()

        admin_user = User(
            id=uuid.uuid4(),
            email=f"admin_{uuid.uuid4().hex[:6]}@timer.io",
            name="Timer Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        op_user = User(
            id=uuid.uuid4(),
            email=f"op_{uuid.uuid4().hex[:6]}@timer.io",
            name="Timer Operator",
            role=UserRole.STATION_OPERATOR,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add_all([admin_user, op_user])
        session.flush()

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Timer Site",
            site_code=f"SITE-{uuid.uuid4().hex[:6].upper()}",
            site_type=SiteType.PUMP_STATION,
            timezone="UTC",
            status=SiteStatus.ACTIVE,
        )
        session.add(site)
        session.flush()

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name="Timer Station",
            station_code=f"STN-{uuid.uuid4().hex[:6].upper()}",
            station_type=StationType.WATER_SUPPLY,
            status=StationStatus.ACTIVE,
        )
        session.add(station)
        session.flush()

        settings = StationSettings(
            id=uuid.uuid4(),
            station_id=station.id,
            default_timer_seconds=1800,
            timezone="Asia/Kolkata",
        )
        session.add(settings)

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name="Timer Controller",
            controller_code=f"CTRL-{uuid.uuid4().hex[:6].upper()}",
            device_uid=f"DEV-{uuid.uuid4().hex[:8].upper()}",
            controller_type=ControllerType.ESP32,
            status=ControllerStatus.ACTIVE,
        )
        session.add(controller)
        session.flush()

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name="Timer Motor",
            motor_code=f"PUMP-{uuid.uuid4().hex[:6].upper()}",
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            status=MotorStatus.ON,
        )
        session.add(motor)
        session.commit()

        return {
            "org_id": org.id,
            "admin_user_id": admin_user.id,
            "op_user_id": op_user.id,
            "site_id": site.id,
            "station_id": station.id,
            "controller_id": controller.id,
            "motor_id": motor.id,
        }


def test_pure_timer_evaluation():
    """Test pure deterministic countdown calculation across all boundary conditions."""
    scheduler = TimerSchedulerService()
    start_time = datetime(2026, 10, 7, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Normal running mid-cycle (10 mins elapsed of 30 mins duration)
    cur_time = start_time + timedelta(seconds=600)
    res = scheduler.evaluate_motor_timer(
        motor_status=MotorStatus.ON,
        started_at=start_time,
        duration_seconds=1800,
        current_time=cur_time,
    )
    assert res.is_running is True
    assert res.elapsed_seconds == 600.0
    assert res.remaining_seconds == 1200.0
    assert res.should_warn_1min is False
    assert res.should_stop is False
    assert res.is_expired is False

    # 2. Exactly 1-minute warning threshold (remaining = 50s <= 60s)
    cur_time = start_time + timedelta(seconds=1750)
    res_warn = scheduler.evaluate_motor_timer(
        motor_status=MotorStatus.ON,
        started_at=start_time,
        duration_seconds=1800,
        current_time=cur_time,
    )
    assert res_warn.remaining_seconds == 50.0
    assert res_warn.should_warn_1min is True
    assert res_warn.should_stop is False

    # 3. Timer Expired threshold (elapsed >= duration)
    cur_time = start_time + timedelta(seconds=1805)
    res_expired = scheduler.evaluate_motor_timer(
        motor_status=MotorStatus.ON,
        started_at=start_time,
        duration_seconds=1800,
        current_time=cur_time,
    )
    assert res_expired.remaining_seconds == 0.0
    assert res_expired.should_warn_1min is False
    assert res_expired.should_stop is True
    assert res_expired.is_expired is True

    # 4. Motor stopped or faulted
    res_stopped = scheduler.evaluate_motor_timer(
        motor_status=MotorStatus.OFF,
        started_at=start_time,
        duration_seconds=1800,
        current_time=cur_time,
    )
    assert res_stopped.is_running is False
    assert res_stopped.should_stop is False
    assert res_stopped.should_warn_1min is False


@pytest.mark.asyncio
async def test_scheduler_process_and_deduplication():
    """Verify check_and_process_motor_timers triggers warnings and dispatches stop with deduplication."""
    h = helper_create_test_hierarchy()
    scheduler = TimerSchedulerService()

    now = datetime.now(timezone.utc)
    start_time = now - timedelta(seconds=1750)

    async with AsyncSessionLocal() as session:
        motor = await session.get(Motor, h["motor_id"])
        motor.created_at = start_time
        motor.updated_at = start_time
        await session.commit()

        # Pass 1: Should trigger warning
        results = await scheduler.check_and_process_motor_timers(session, current_time=now)
        assert len(results) >= 1
        target_res = next((r for r in results if r.motor_id == h["motor_id"]), None)
        assert target_res is not None
        assert target_res.warning_triggered is True

        # Pass 2: Same timestamp/cycle -> warning should NOT be duplicated
        results_dup = await scheduler.check_and_process_motor_timers(session, current_time=now)
        target_dup = next((r for r in results_dup if r.motor_id == h["motor_id"]), None)
        assert target_dup is not None
        assert target_dup.warning_triggered is False

        # Pass 3: Time advances to 1810s (expired) -> STOP command dispatched
        expired_time = start_time + timedelta(seconds=1810)
        results_stop = await scheduler.check_and_process_motor_timers(session, current_time=expired_time)
        target_stop = next((r for r in results_stop if r.motor_id == h["motor_id"]), None)
        assert target_stop is not None
        assert target_stop.stop_dispatched is True


@pytest.mark.asyncio
async def test_schedule_service_crud():
    """Verify schedule service CRUD with JSON metadata encoding."""
    h = helper_create_test_hierarchy()

    async with AsyncSessionLocal() as session:
        # 1. Create Schedule
        create_req = ScheduleCreate(
            station_id=h["station_id"],
            motor_id=h["motor_id"],
            name="Morning Garden Water",
            days_of_week=["MON", "WED", "FRI"],
            start_time="07:30",
            duration_seconds=900,
            is_active=True,
        )
        created = await create_schedule(session, create_req, creator_id=h["admin_user_id"])
        assert created.name == "Morning Garden Water"
        assert created.days_of_week == ["MON", "WED", "FRI"]
        assert created.start_time == "07:30"
        assert created.duration_seconds == 900
        assert created.is_active is True

        # 2. List Schedules
        schedules = await list_schedules_for_station(session, h["station_id"])
        assert len(schedules) >= 1
        assert any(s.id == created.id for s in schedules)

        # 3. Update Schedule
        rule_entity = await session.get(AutomationRule, created.id)
        update_req = ScheduleUpdate(
            name="Updated Garden Water",
            duration_seconds=1200,
            start_time="08:00",
        )
        updated = await update_schedule(session, rule_entity, update_req)
        assert updated.name == "Updated Garden Water"
        assert updated.duration_seconds == 1200
        assert updated.start_time == "08:00"

        # 4. Delete Schedule
        await delete_schedule(session, rule_entity)
        remaining = await list_schedules_for_station(session, h["station_id"])
        assert not any(s.id == created.id for s in remaining)


def test_schedules_api_rbac_and_isolation(client: TestClient):
    """Verify schedule API RBAC permissions and multi-tenant isolation."""
    h = helper_create_test_hierarchy()
    admin_token = create_access_token(h["admin_user_id"], extra_claims={"role": UserRole.ORGANIZATION_ADMIN})
    operator_token = create_access_token(h["op_user_id"], extra_claims={"role": UserRole.STATION_OPERATOR})

    # 1. ORG_ADMIN can create schedule
    payload = {
        "station_id": str(h["station_id"]),
        "motor_id": str(h["motor_id"]),
        "name": "Admin Daily Schedule",
        "days_of_week": ["MON", "TUE", "WED"],
        "start_time": "06:00",
        "duration_seconds": 1800,
        "is_active": True,
    }
    resp = client.post(
        f"/api/v1/stations/{h['station_id']}/schedules",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    created_id = resp.json()["id"]

    # 2. STATION_OPERATOR can read schedules
    list_resp = client.get(
        f"/api/v1/stations/{h['station_id']}/schedules",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 3. STATION_OPERATOR cannot delete schedule (403 Forbidden)
    del_resp = client.delete(
        f"/api/v1/stations/{h['station_id']}/schedules/{created_id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert del_resp.status_code == 403

    # 4. IDOR test: Foreign station query returns 404
    foreign_station_id = uuid.uuid4()
    foreign_resp = client.get(
        f"/api/v1/stations/{foreign_station_id}/schedules",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert foreign_resp.status_code == 404


@pytest.mark.asyncio
async def test_schedule_execution_engine_and_safety_overrides():
    """Verify check_and_execute_schedules executes active schedules and respects Phase 10 safety state."""
    h = helper_create_test_hierarchy()
    scheduler = TimerSchedulerService()

    # Fixed time: Monday 06:00 UTC (2026-10-12 is a Monday)
    simulated_now = datetime(2026, 10, 12, 6, 0, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        # Create an active schedule for Monday 06:00
        req = ScheduleCreate(
            station_id=h["station_id"],
            motor_id=h["motor_id"],
            name="Morning Irrigation",
            days_of_week=["MON", "WED", "FRI"],
            start_time="06:00",
            duration_seconds=1200,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=h["admin_user_id"])

        # Set motor to OFF so it's ready to start
        motor = await session.get(Motor, h["motor_id"])
        motor.status = MotorStatus.OFF
        await session.commit()

        # Pass 1: Should execute and dispatch START
        results = await scheduler.check_and_execute_schedules(session, current_time=simulated_now)
        assert len(results) >= 1
        executed_res = [r for r in results if r.schedule_id == sched.id][0]
        assert executed_res.executed is True
        assert executed_res.reason == "SCHEDULED_START_DISPATCHED"

        # Pass 2: Deduplication in the same minute window -> not executed again
        results_dupe = await scheduler.check_and_execute_schedules(session, current_time=simulated_now)
        dupe_res = [r for r in results_dupe if r.schedule_id == sched.id]
        assert len(dupe_res) == 0

        # Pass 3: Safety Override — Set motor to FAULT
        new_scheduler = TimerSchedulerService()  # fresh state
        motor.status = MotorStatus.FAULT
        await session.commit()

        results_safety = await new_scheduler.check_and_execute_schedules(session, current_time=simulated_now)
        fault_res = [r for r in results_safety if r.schedule_id == sched.id][0]
        assert fault_res.executed is False
        assert "SAFETY_OVERRIDE" in fault_res.reason
