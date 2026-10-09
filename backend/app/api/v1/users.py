"""
HydraControl — User & Business Subscription Management API
Allows Organization Admins and Super Admins to manage users, assign roles, and administer business subscriptions.
"""
import uuid
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.db.session import get_db
from app.api.deps import get_current_user, require_roles, get_current_organization
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.motor import Motor
from app.models.station import Station
from app.models.site import Site
from app.core.security import get_password_hash
from app.schemas.user import (
    UserAdminCreate,
    UserAdminUpdate,
    UserDetailResponse,
    SubscriptionPlanInfo,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
)

router = APIRouter(tags=["User & Subscription Management"])

# Defined Subscription Plans Catalogue
PLANS = {
    "STARTER": SubscriptionPlanInfo(
        tier="STARTER",
        name="Hydra Starter",
        price_monthly=29.0,
        price_annual=290.0,
        max_motors=5,
        max_stations=2,
        max_users=3,
        features=[
            "Up to 5 Motor Automation Units",
            "2 Station Gateways",
            "3 Operator Accounts",
            "Real-time Telemetry & Basic Scheduling",
            "Email Alert Notifications",
        ],
    ),
    "PRO": SubscriptionPlanInfo(
        tier="PRO",
        name="Hydra Professional",
        price_monthly=79.0,
        price_annual=790.0,
        max_motors=25,
        max_stations=10,
        max_users=15,
        features=[
            "Up to 25 Motor Automation Units",
            "10 Station Gateways",
            "15 Operator & Manager Accounts",
            "Advanced Time-of-Day Scheduling & Auto-Cutoff",
            "Turbidity & Dry-Run Safety Protection",
            "Real-time WebSocket Buzzer & Audio Alerts",
            "Priority Support & Multi-Site Sync",
        ],
    ),
    "ENTERPRISE": SubscriptionPlanInfo(
        tier="ENTERPRISE",
        name="Hydra Enterprise Fleet",
        price_monthly=199.0,
        price_annual=1990.0,
        max_motors=100,
        max_stations=50,
        max_users=50,
        features=[
            "Unlimited / Up to 100 Motor Units",
            "50 Station Gateways",
            "50 User Accounts with Custom RBAC",
            "Complete Safety Interlock & Forensics Audit Trail",
            "Multi-Tenant Cross-Site Fleet Dashboard",
            "Dedicated Support Engineer & 99.99% SLA",
            "Custom ESP32 Firmware OTA Upgrades",
        ],
    ),
}

# In-memory subscription store for organization tiers: org_id -> tier
_org_subscriptions: dict = {}


@router.get("", response_model=List[UserDetailResponse])
async def list_users(
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])),
    session: AsyncSession = Depends(get_db),
):
    """
    List all users in the authenticated organization.
    SUPER_ADMIN can see all users.
    """
    stmt = select(User)
    if current_user.role != UserRole.SUPER_ADMIN:
        if current_user.organization_id is None:
            return [current_user]
        stmt = stmt.where(User.organization_id == current_user.organization_id)

    res = await session.execute(stmt)
    return res.scalars().all()


@router.post("", response_model=UserDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserAdminCreate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Create/Invite a new user with an assigned role into the organization.
    """
    normalized_email = req.email.lower().strip()
    stmt = select(User).where(User.email == normalized_email)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    org_id = req.organization_id if current_user.role == UserRole.SUPER_ADMIN and req.organization_id else current_user.organization_id

    new_user = User(
        id=uuid.uuid4(),
        name=req.name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(req.password),
        role=req.role,
        is_active=True,
        organization_id=org_id,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user


@router.patch("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: uuid.UUID,
    req: UserAdminUpdate,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Update a user's role, name, or active status.
    """
    stmt = select(User).where(User.id == user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role != UserRole.SUPER_ADMIN and user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if req.name is not None:
        user.name = req.name.strip()
    if req.role is not None:
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active

    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a user from the organization.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account.")

    stmt = select(User).where(User.id == user_id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role != UserRole.SUPER_ADMIN and user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await session.delete(user)
    await session.commit()


# ==============================================================================
# Subscription Management
# ==============================================================================

@router.get("/subscriptions/plans", response_model=List[SubscriptionPlanInfo])
async def get_subscription_plans():
    """Returns available platform subscription plans and pricing."""
    return list(PLANS.values())


@router.get("/subscriptions/current", response_model=SubscriptionResponse)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Returns current organization's subscription status, active tier, and device quotas.
    """
    org_id = current_user.organization_id
    org_name = "Default Organization"
    org_code = "HYDRA-DEFAULT"

    if org_id:
        org_stmt = select(Organization).where(Organization.id == org_id)
        org_res = await session.execute(org_stmt)
        org = org_res.scalar_one_or_none()
        if org:
            org_name = org.name
            org_code = org.organization_code

    tier = _org_subscriptions.get(str(org_id), "PRO") if org_id else "PRO"
    plan = PLANS.get(tier, PLANS["PRO"])

    # Count current active entities for this organization
    motor_count = 1
    station_count = 1
    user_count = 1

    try:
        if org_id:
            # count users
            u_stmt = select(func.count(User.id)).where(User.organization_id == org_id)
            user_count = (await session.execute(u_stmt)).scalar() or 1

            # count stations
            s_stmt = select(func.count(Station.id)).join(Site).where(Site.organization_id == org_id)
            station_count = (await session.execute(s_stmt)).scalar() or 1

            # count motors
            m_stmt = (
                select(func.count(Motor.id))
                .join(Station, Motor.station_id == Station.id)
                .join(Site, Station.site_id == Site.id)
                .where(Site.organization_id == org_id)
            )
            motor_count = (await session.execute(m_stmt)).scalar() or 1
    except Exception:
        pass

    renewal_dt = (datetime.now(timezone.utc) + timedelta(days=335)).strftime("%B %d, %Y")

    return SubscriptionResponse(
        organization_id=org_id or uuid.uuid4(),
        organization_name=org_name,
        organization_code=org_code,
        tier=plan.tier,
        status="ACTIVE",
        max_motors=plan.max_motors,
        current_motors=motor_count,
        max_stations=plan.max_stations,
        current_stations=station_count,
        max_users=plan.max_users,
        current_users=user_count,
        billing_cycle="ANNUAL",
        renewal_date=renewal_dt,
        features=plan.features,
    )


@router.put("/subscriptions/current", response_model=SubscriptionResponse)
async def update_subscription_plan(
    req: SubscriptionUpdateRequest,
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])),
    session: AsyncSession = Depends(get_db),
):
    """
    Upgrade or switch organization subscription tier.
    """
    tier_upper = req.tier.upper()
    if tier_upper not in PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid subscription tier '{req.tier}'. Allowed tiers: {list(PLANS.keys())}",
        )

    org_id = current_user.organization_id
    if org_id:
        _org_subscriptions[str(org_id)] = tier_upper

    return await get_current_subscription(current_user=current_user, session=session)
