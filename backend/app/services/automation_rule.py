"""Service layer for AutomationRule management (Phase 12 - Wave 2A)."""

import uuid
from typing import Sequence, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from app.models.automation_rule import (
    AutomationRule,
    AutomationRuleStatus,
)
from app.models.station import Station
from app.models.site import Site
from app.models.user import User, UserRole
from app.schemas.automation_rule import AutomationRuleCreate, AutomationRuleUpdate


class AutomationRuleNotFoundException(Exception):
    pass


class AutomationRuleValidationException(Exception):
    pass


async def get_automation_rule_by_id(
    session: AsyncSession,
    rule_id: uuid.UUID,
) -> Optional[AutomationRule]:
    stmt = select(AutomationRule).where(AutomationRule.id == rule_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()


async def list_automation_rules_for_station(
    session: AsyncSession,
    station_id: uuid.UUID,
    status: Optional[AutomationRuleStatus] = None,
) -> Sequence[AutomationRule]:
    stmt = select(AutomationRule).where(AutomationRule.station_id == station_id)
    if status is not None:
        stmt = stmt.where(AutomationRule.status == status)
    res = await session.execute(stmt)
    return res.scalars().all()


async def create_automation_rule(
    session: AsyncSession,
    req: AutomationRuleCreate,
    creator_id: Optional[uuid.UUID] = None,
) -> AutomationRule:
    rule = AutomationRule(
        id=uuid.uuid4(),
        station_id=req.station_id,
        name=req.name.strip(),
        description=req.description.strip() if req.description else None,
        rule_type=req.rule_type,
        status=req.status or AutomationRuleStatus.ACTIVE,
        sensor_id=req.sensor_id,
        operator=req.operator,
        threshold_value=req.threshold_value,
        threshold_unit=req.threshold_unit.strip() if req.threshold_unit else None,
        duration_seconds=req.duration_seconds,
        motor_id=req.motor_id,
        action=req.action,
        cooldown_seconds=req.cooldown_seconds,
        created_by=creator_id,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_automation_rule(
    session: AsyncSession,
    rule: AutomationRule,
    req: AutomationRuleUpdate,
) -> AutomationRule:
    if req.name is not None:
        rule.name = req.name.strip()
    if req.description is not None:
        rule.description = req.description.strip() if req.description else None
    if req.rule_type is not None:
        rule.rule_type = req.rule_type
    if req.status is not None:
        rule.status = req.status
    if req.sensor_id is not None:
        rule.sensor_id = req.sensor_id
    if req.operator is not None:
        rule.operator = req.operator
    if req.threshold_value is not None:
        rule.threshold_value = req.threshold_value
    if req.threshold_unit is not None:
        rule.threshold_unit = req.threshold_unit.strip() if req.threshold_unit else None
    if req.duration_seconds is not None:
        rule.duration_seconds = req.duration_seconds
    if req.motor_id is not None:
        rule.motor_id = req.motor_id
    if req.action is not None:
        rule.action = req.action
    if req.cooldown_seconds is not None:
        rule.cooldown_seconds = req.cooldown_seconds

    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_automation_rule(
    session: AsyncSession,
    rule: AutomationRule,
) -> None:
    await session.delete(rule)
    await session.commit()
