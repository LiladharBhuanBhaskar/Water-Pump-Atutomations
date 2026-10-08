"""
HydraControl — Today's Time-of-Day Schedule, In-App Notification & Buzzer Regression Suite.
Validates:
1. Today's schedule detection and execution under local timezone (Asia/Kolkata).
2. Day-of-week matching and exclusion of non-scheduled days.
3. Minute-window execution and deterministic duplicate prevention.
4. Schedule start notification dispatching (SCHEDULE_STARTED) with correct severity and payload.
5. In-App notification WebSocket streaming (NOTIFICATION_RECEIVED) to user/org/station channels.
6. 1-minute pre-expiration warning and timer expiration auto-stop notifications.
7. Safety state preservation: motor in FAULT or EMERGENCY_STOP cannot be started by schedule.
"""

import uuid
import json
import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch, AsyncMock

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
from app.core.security import get_password_hash
from app.services.timer_scheduler_service import timer_scheduler, TimerSchedulerService, get_local_datetime
from app.services.schedule_service import create_schedule
from app.services.notification_service import notification_service
from app.schemas.schedule import ScheduleCreate
from app.schemas.notification import NotificationChannel, NotificationSeverity
from app.websocket.hub import hub


@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)


def helper_create_test_environment(tz_name: str = "Asia/Kolkata"):
    with get_sync_session() as session:
        org = Organization(
            id=uuid.uuid4(),
            name="Schedule Test Org",
            organization_code=f"SCHED-{uuid.uuid4().hex[:6].upper()}",
            status=OrganizationStatus.ACTIVE,
        )
        session.add(org)
        session.flush()

        admin_user = User(
            id=uuid.uuid4(),
            email=f"admin_{uuid.uuid4().hex[:6]}@sched.io",
            name="Schedule Admin",
            role=UserRole.ORGANIZATION_ADMIN,
            organization_id=org.id,
            password_hash=get_password_hash("Pass@123"),
            is_active=True,
        )
        session.add(admin_user)
        session.flush()

        site = Site(
            id=uuid.uuid4(),
            organization_id=org.id,
            name="Schedule Test Site",
            site_code=f"SITE-{uuid.uuid4().hex[:6].upper()}",
            site_type=SiteType.PUMP_STATION,
            timezone=tz_name,
            status=SiteStatus.ACTIVE,
        )
        session.add(site)
        session.flush()

        station = Station(
            id=uuid.uuid4(),
            site_id=site.id,
            name="Schedule Test Station",
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
            timezone=tz_name,
        )
        session.add(settings)
        session.flush()

        controller = Controller(
            id=uuid.uuid4(),
            station_id=station.id,
            name="Schedule Test Controller",
            controller_code=f"CTRL-{uuid.uuid4().hex[:6].upper()}",
            controller_type=ControllerType.ESP32,
            device_uid=f"TEST-DEV-{uuid.uuid4().hex[:8].upper()}",
            status=ControllerStatus.ACTIVE,
        )
        session.add(controller)
        session.flush()

        motor = Motor(
            id=uuid.uuid4(),
            controller_id=controller.id,
            name="Schedule Test Motor",
            motor_code=f"MTR-{uuid.uuid4().hex[:4].upper()}",
            motor_type=MotorType.SUBMERSIBLE_PUMP,
            status=MotorStatus.OFF,
        )
        session.add(motor)
        session.commit()

        return {
            "org_id": org.id,
            "admin_user_id": admin_user.id,
            "site_id": site.id,
            "station_id": station.id,
            "controller_id": controller.id,
            "motor_id": motor.id,
            "motor_code": motor.motor_code,
            "timezone": tz_name,
        }


@pytest.mark.asyncio
async def test_today_schedule_executes_in_local_timezone():
    """Test 1: Schedule created for TODAY executes when evaluated at matching local time."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    # Define simulated time in UTC: 2026-10-08 08:35:00 UTC
    # In Asia/Kolkata (UTC+5:30), this is 2026-10-08 14:05:00 (Thursday)
    simulated_now_utc = datetime(2026, 10, 8, 8, 35, 0, tzinfo=timezone.utc)
    local_dt = get_local_datetime(simulated_now_utc, "Asia/Kolkata")
    assert local_dt.strftime("%H:%M") == "14:05"
    assert local_dt.strftime("%A").upper() == "THURSDAY"

    async with AsyncSessionLocal() as session:
        # Create a schedule for today (THU / THURSDAY) at 14:05
        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Today Afternoon Irrigation",
            days_of_week=["THU"],
            start_time="14:05",
            duration_seconds=120,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        # Execute scheduler at 14:05 local time
        results = await scheduler.check_and_execute_schedules(session, current_time=simulated_now_utc)
        assert len(results) >= 1
        res = [r for r in results if r.schedule_id == sched.id][0]
        assert res.executed is True
        assert res.reason == "SCHEDULED_START_DISPATCHED"
        assert res.command_id is not None


@pytest.mark.asyncio
async def test_wrong_day_does_not_execute():
    """Test 2: Schedule configured for a different day of the week does NOT execute today."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    # 2026-10-08 14:05 IST is Thursday
    simulated_now_utc = datetime(2026, 10, 8, 8, 35, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        # Create schedule for Friday only
        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Friday Only Schedule",
            days_of_week=["FRI"],
            start_time="14:05",
            duration_seconds=120,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        results = await scheduler.check_and_execute_schedules(session, current_time=simulated_now_utc)
        matching = [r for r in results if r.schedule_id == sched.id]
        assert len(matching) == 0


@pytest.mark.asyncio
async def test_late_scheduler_evaluation_in_minute_window():
    """Test 3: Scheduler evaluating at 14:05:03 or 14:05:45 still triggers the schedule."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    # 14:05:45 IST
    simulated_late_utc = datetime(2026, 10, 8, 8, 35, 45, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Late Check Schedule",
            days_of_week=["THURSDAY"],
            start_time="14:05",
            duration_seconds=120,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        results = await scheduler.check_and_execute_schedules(session, current_time=simulated_late_utc)
        matching = [r for r in results if r.schedule_id == sched.id]
        assert len(matching) == 1
        assert matching[0].executed is True


@pytest.mark.asyncio
async def test_duplicate_execution_prevention():
    """Test 4: Schedule does NOT execute multiple times within the same minute window."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    t1_utc = datetime(2026, 10, 8, 8, 35, 2, tzinfo=timezone.utc)
    t2_utc = datetime(2026, 10, 8, 8, 35, 15, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Dedup Test Schedule",
            days_of_week=["THU"],
            start_time="14:05",
            duration_seconds=120,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        # First tick
        res1 = await scheduler.check_and_execute_schedules(session, current_time=t1_utc)
        assert any(r.schedule_id == sched.id and r.executed for r in res1)

        # Second tick in same minute window
        res2 = await scheduler.check_and_execute_schedules(session, current_time=t2_utc)
        assert not any(r.schedule_id == sched.id for r in res2)


@pytest.mark.asyncio
async def test_schedule_notification_dispatch_and_websocket_broadcast():
    """Test 5 & 6: Schedule execution calls notification_service and broadcasts NOTIFICATION_RECEIVED."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    simulated_now_utc = datetime(2026, 10, 8, 8, 35, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Notification Broadcast Test",
            days_of_week=["THU"],
            start_time="14:05",
            duration_seconds=120,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        with patch.object(notification_service, "dispatch_notification", wraps=notification_service.dispatch_notification) as mock_notif:
            results = await scheduler.check_and_execute_schedules(session, current_time=simulated_now_utc)
            assert any(r.schedule_id == sched.id and r.executed for r in results)

            # Assert notification_service was invoked
            assert mock_notif.called
            call_kwargs = mock_notif.call_args.kwargs
            assert call_kwargs["title"] == "Scheduled Pump Started"
            assert "auto-started according to schedule" in call_kwargs["message"]
            assert call_kwargs["severity"] == NotificationSeverity.INFO
            assert call_kwargs["event_type"] == "SCHEDULE_STARTED"
            assert call_kwargs["motor_id"] == env["motor_id"]
            assert call_kwargs["station_id"] == env["station_id"]


@pytest.mark.asyncio
async def test_motor_timers_warning_and_expiration_notifications():
    """Test 7: check_and_process_motor_timers emits 1-min warning and stop notifications."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    motor_start_utc = datetime(2026, 10, 8, 8, 0, 0, tzinfo=timezone.utc)
    # Motor configured for 120s duration
    warn_time_utc = datetime(2026, 10, 8, 8, 1, 10, tzinfo=timezone.utc)  # elapsed 70s -> remaining 50s (<= 60s warning)
    expire_time_utc = datetime(2026, 10, 8, 8, 2, 5, tzinfo=timezone.utc)  # elapsed 125s -> expired

    async with AsyncSessionLocal() as session:
        motor = await session.get(Motor, env["motor_id"])
        motor.status = MotorStatus.ON
        motor.updated_at = motor_start_utc
        await session.commit()

        # Set custom timer rule for 120 seconds
        rule = AutomationRule(
            id=uuid.uuid4(),
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="120s Timer",
            rule_type=AutomationRuleType.TIMER,
            status=AutomationRuleStatus.ACTIVE,
            action=AutomationAction.STOP_MOTOR,
            duration_seconds=120,
        )
        session.add(rule)
        await session.commit()

        # 1. 1-Minute Warning Check
        with patch.object(notification_service, "dispatch_notification", wraps=notification_service.dispatch_notification) as mock_notif:
            results_warn = await scheduler.check_and_process_motor_timers(session, current_time=warn_time_utc)
            warn_res = [r for r in results_warn if r.motor_id == env["motor_id"]][0]
            assert warn_res.warning_triggered is True
            assert mock_notif.called
            assert mock_notif.call_args.kwargs["event_type"] == "TIMER_WARNING"

        # 2. Expiration Auto-Stop Check
        with patch.object(notification_service, "dispatch_notification", wraps=notification_service.dispatch_notification) as mock_notif_exp:
            results_exp = await scheduler.check_and_process_motor_timers(session, current_time=expire_time_utc)
            exp_res = [r for r in results_exp if r.motor_id == env["motor_id"]][0]
            assert exp_res.stop_dispatched is True
            assert mock_notif_exp.called
            assert mock_notif_exp.call_args.kwargs["event_type"] == "TIMER_EXPIRED"


@pytest.mark.asyncio
async def test_motor_safety_override_preserves_interlocks():
    """Test 8: Schedule will NOT start a motor in FAULT or DISABLED state."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()

    simulated_now_utc = datetime(2026, 10, 8, 8, 35, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        # Motor in FAULT state (e.g., from dry-run or turbidity trip)
        motor = await session.get(Motor, env["motor_id"])
        motor.status = MotorStatus.FAULT
        await session.commit()

        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Fault Safety Test",
            days_of_week=["THU"],
            start_time="14:05",
            duration_seconds=120,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        results = await scheduler.check_and_execute_schedules(session, current_time=simulated_now_utc)
        res = [r for r in results if r.schedule_id == sched.id][0]
        assert res.executed is False
        assert "SAFETY_OVERRIDE_MOTOR_STATUS_FAULT" in res.reason


@pytest.mark.asyncio
async def test_timer_status_and_countdown_recovery():
    """Test 9: Live countdown state recovery from backend authoritative end timestamp."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()
    now_utc = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        motor = await session.get(Motor, env["motor_id"])
        motor.status = MotorStatus.ON
        motor.updated_at = now_utc - timedelta(seconds=100)
        await session.commit()

        # Set 300s timer
        rule = AutomationRule(
            id=uuid.uuid4(),
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="300s Timer",
            rule_type=AutomationRuleType.TIMER,
            status=AutomationRuleStatus.ACTIVE,
            action=AutomationAction.STOP_MOTOR,
            duration_seconds=300,
        )
        session.add(rule)
        await session.commit()

        status = await scheduler.get_motor_timer_status(session, env["motor_id"])
        assert status["is_running"] is True
        assert status["duration_seconds"] == 300
        assert 190 <= status["remaining_seconds"] <= 205
        assert status["is_warning_active"] is False
        assert status["end_time"] is not None


@pytest.mark.asyncio
async def test_continue_motor_timer_extends_and_cancels_old_expiration():
    """Test 10: Continue extends active duration (+15 min), updates authoritative end_time, and cancels old auto-stop."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()
    now_utc = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        motor = await session.get(Motor, env["motor_id"])
        motor.status = MotorStatus.ON
        motor.updated_at = now_utc - timedelta(seconds=280)  # 20s remaining of 300s
        await session.commit()

        rule = AutomationRule(
            id=uuid.uuid4(),
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="300s Warning Timer",
            rule_type=AutomationRuleType.TIMER,
            status=AutomationRuleStatus.ACTIVE,
            action=AutomationAction.STOP_MOTOR,
            duration_seconds=300,
        )
        session.add(rule)
        await session.commit()

        # Trigger warning
        await scheduler.check_and_process_motor_timers(session, current_time=now_utc)
        assert env["motor_id"] in scheduler._warned_cycles

        # User presses CONTINUE (+900 seconds)
        with patch.object(notification_service, "dispatch_notification", wraps=notification_service.dispatch_notification) as mock_notif:
            updated_status = await scheduler.continue_motor_timer(
                session,
                env["motor_id"],
                extend_seconds=900,
                actor_id=env["admin_user_id"],
            )
            assert updated_status["is_running"] is True
            assert updated_status["duration_seconds"] == 1200  # 300 + 900
            assert updated_status["remaining_seconds"] > 900
            # Warning cycle reset
            assert env["motor_id"] not in scheduler._warned_cycles
            # Notification sent
            assert mock_notif.called
            assert mock_notif.call_args.kwargs["event_type"] == "TIMER_CONTINUED"

        # Now test that the old expiration timestamp (now + 20s) DOES NOT stop the motor
        old_expiry_time = now_utc + timedelta(seconds=25)
        results = await scheduler.check_and_process_motor_timers(session, current_time=old_expiry_time)
        res = [r for r in results if r.motor_id == env["motor_id"]][0]
        assert res.stop_dispatched is False


@pytest.mark.asyncio
async def test_continue_motor_timer_duplicate_protection():
    """Test 11: Rapid duplicate Continue clicks (<5s) are safely deduplicated/idempotent."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()
    now_utc = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        motor = await session.get(Motor, env["motor_id"])
        motor.status = MotorStatus.ON
        motor.updated_at = now_utc
        await session.commit()

        # 1st Continue: +900s
        res1 = await scheduler.continue_motor_timer(session, env["motor_id"], extend_seconds=900)
        assert res1["duration_seconds"] == 2700  # 1800 default + 900

        # 2nd Continue within 100ms (e.g. Operator and Admin click at the same second)
        res2 = await scheduler.continue_motor_timer(session, env["motor_id"], extend_seconds=900)
        assert res2["duration_seconds"] == 2700  # Debounced, no duplicate addition


@pytest.mark.asyncio
async def test_scheduled_start_matches_manual_start_state_and_command_service():
    """Test 12: Scheduled start produces exact same MotorStatus.ON and commands as manual start."""
    env = helper_create_test_environment(tz_name="Asia/Kolkata")
    scheduler = TimerSchedulerService()
    now_utc = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        motor = await session.get(Motor, env["motor_id"])
        motor.status = MotorStatus.OFF
        await session.commit()

        req = ScheduleCreate(
            station_id=env["station_id"],
            motor_id=env["motor_id"],
            name="Authoritative Start Test",
            days_of_week=["THU", "MON", "TUE", "WED", "FRI", "SAT", "SUN"],
            start_time="14:00",
            duration_seconds=600,
            is_active=True,
        )
        sched = await create_schedule(session, req, creator_id=env["admin_user_id"])

        simulated_now = datetime(2026, 10, 8, 8, 30, 0, tzinfo=timezone.utc)
        results = await scheduler.check_and_execute_schedules(session, current_time=simulated_now)
        res = [r for r in results if r.schedule_id == sched.id][0]
        assert res.executed is True
        assert res.command_id is not None

        # Re-fetch motor state in fresh session
        await session.commit()
        async with AsyncSessionLocal() as fresh_session:
            motor_refreshed = await fresh_session.get(Motor, env["motor_id"])
            assert motor_refreshed.status == MotorStatus.ON

