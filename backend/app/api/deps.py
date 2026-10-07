import uuid
from typing import List, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus


# This matches the endpoint we will build later
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    import uuid
    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
        
    return user


def require_roles(allowed_roles: List[UserRole]) -> Callable:
    """
    Dependency factory to check if the current user has one of the allowed roles.
    Returns the user if authorized, otherwise raises HTTP 403 Forbidden.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return role_checker


async def get_current_organization(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
) -> Organization:
    """
    Retrieves and validates the active Organization for the authenticated user.
    Ensures that tenant context is strictly derived from the authenticated User.organization_id.
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any organization"
        )

    stmt = select(Organization).where(Organization.id == current_user.organization_id)
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    if org.status != OrganizationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Organization is {org.status.value.lower()}"
        )

    return org


async def get_current_site(
    site_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_organization),
    session: AsyncSession = Depends(get_db)
) -> "Site":
    """
    Retrieves and validates that the requested site exists within the user's authenticated organization,
    and that the user has appropriate site-level authorization based on site operational status and role.
    """
    from app.models.site import Site
    from app.services.site_auth import validate_site_access_policy
    from app.services.tenant import get_org_scoped_resource

    site = await get_org_scoped_resource(session, Site, site_id, current_org.id)
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    validate_site_access_policy(site, current_user)
    return site


