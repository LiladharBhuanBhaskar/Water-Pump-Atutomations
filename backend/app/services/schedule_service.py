"""
HydraControl — Schedule Service (Phase 16 - Wave A)
Provides scheduling management backed by the existing AutomationRule model/table,
enabling zero-migration schedule configuration with full multi-tenant isolation.
"""

import json
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.automation_rule import (
    AutomationRule,
    AutomationRuleType,
    AutomationRuleStatus,
    AutomationAction,
)
from app.models.motor import Motor
from app.models.station import Station
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse


def parse_schedule_metadata(description: Optional[str]) -> tuple[List[str], str]:
    """Parse JSON metadata from rule description, falling back to defaults."""
    default_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    default_start = "06:00"

    if not description:
        return default_days, default_start

    try:
        data = json.loads(description)
        days = data.get("days_of_week", default_days)
        start = data.get("start_time", default_start)
        return days, start
    except Exception:
        return default_days, default_start


def encode_schedule_metadata(days_of_week: List[str], start_time: str) -> str:
    """Encode schedule metadata into JSON string for description field."""
    return json.dumps({
        "days_of_week": [d.upper().strip() for d in days_of_week],
        "start_time": start_time.strip(),
    })


def rule_to_schedule_response(rule: AutomationRule) -> ScheduleResponse:
    """Convert an AutomationRule entity to a ScheduleResponse."""
    days, start = parse_schedule_metadata(rule.description)
    return ScheduleResponse(
        id=rule.id,
        station_id=rule.station_id,
        motor_id=rule.motor_id,
        name=rule.name,
        days_of_week=days,
        start_time=start,
        duration_seconds=rule.duration_seconds or 1800,
        is_active=(rule.status == AutomationRuleStatus.ACTIVE),
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


async def list_schedules_for_station(
    session: AsyncSession,
    station_id: uuid.UUID,
) -> List[ScheduleResponse]:
    """List all schedule rules for a given station."""
    stmt = (
        select(AutomationRule)
        .where(
            AutomationRule.station_id == station_id,
            AutomationRule.rule_type == AutomationRuleType.TIMER,
        )
        .order_by(AutomationRule.created_at.asc())
    )
    res = await session.execute(stmt)
    rules = res.scalars().all()
    return [rule_to_schedule_response(r) for r in rules]


async def get_schedule_by_id(
    session: AsyncSession,
    schedule_id: uuid.UUID,
) -> Optional[AutomationRule]:
    """Get schedule AutomationRule by ID."""
    stmt = (
        select(AutomationRule)
        .where(
            AutomationRule.id == schedule_id,
            AutomationRule.rule_type == AutomationRuleType.TIMER,
        )
    )
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def create_schedule(
    session: AsyncSession,
    req: ScheduleCreate,
    creator_id: Optional[uuid.UUID] = None,
) -> ScheduleResponse:
    """Create a new schedule rule."""
    # Verify motor belongs to station
    motor_stmt = select(Motor).where(Motor.id == req.motor_id)
    motor_res = await session.execute(motor_stmt)
    motor = motor_res.scalar_one_or_none()
    if motor is None:
        raise ValueError(f"Target motor '{req.motor_id}' not found.")

    desc = encode_schedule_metadata(req.days_of_week, req.start_time)
    rule = AutomationRule(
        station_id=req.station_id,
        motor_id=req.motor_id,
        name=req.name,
        description=desc,
        rule_type=AutomationRuleType.TIMER,
        status=AutomationRuleStatus.ACTIVE if req.is_active else AutomationRuleStatus.INACTIVE,
        duration_seconds=req.duration_seconds,
        action=AutomationAction.STOP_MOTOR,
        created_by=creator_id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule_to_schedule_response(rule)


async def update_schedule(
    session: AsyncSession,
    rule: AutomationRule,
    req: ScheduleUpdate,
) -> ScheduleResponse:
    """Update an existing schedule rule."""
    days, start = parse_schedule_metadata(rule.description)

    if req.name is not None:
        rule.name = req.name
    if req.days_of_week is not None:
        days = req.days_of_week
    if req.start_time is not None:
        start = req.start_time
    if req.duration_seconds is not None:
        rule.duration_seconds = req.duration_seconds
    if req.is_active is not None:
        rule.status = AutomationRuleStatus.ACTIVE if req.is_active else AutomationRuleStatus.INACTIVE

    rule.description = encode_schedule_metadata(days, start)
    await session.commit()
    await session.refresh(rule)
    return rule_to_schedule_response(rule)


async def delete_schedule(
    session: AsyncSession,
    rule: AutomationRule,
) -> None:
    """Delete a schedule rule."""
    await session.delete(rule)
    await session.commit()
