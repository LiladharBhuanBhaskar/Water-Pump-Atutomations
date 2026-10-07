from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    UserRegistrationRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    RefreshTokenRequest,
)
from app.api.deps import get_current_user, require_roles, get_current_organization
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.services.auth import (
    register_user, 
    authenticate_user, 
    UserAlreadyExistsException, 
    InvalidCredentialsException, 
    InactiveUserException
)
from app.services.token_service import token_service
from app.core.rate_limiter import rate_limit

router = APIRouter(tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: UserRegistrationRequest, 
    session: AsyncSession = Depends(get_db)
):
    try:
        user = await register_user(session, req)
        return user
    except UserAlreadyExistsException:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        )

@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, key_prefix="login"))]
)
async def login(
    req: LoginRequest,
    session: AsyncSession = Depends(get_db)
):
    try:
        token_response = await authenticate_user(session, req)
        return token_response
    except InvalidCredentialsException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except InactiveUserException:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(req: RefreshTokenRequest):
    """Rotates refresh token and returns a new Access and Refresh Token pair."""
    try:
        new_access, new_refresh, _ = token_service.rotate_refresh_token(req.refresh_token)
        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(req: RefreshTokenRequest):
    """Revokes refresh token for secure session termination."""
    token_service.revoke_refresh_token(req.refresh_token)
    return {"status": "success", "detail": "Session revoked"}

@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(get_current_user)
):
    return current_user

@router.get("/organization")
async def read_users_organization(
    current_org: Organization = Depends(get_current_organization)
):
    return {
        "id": str(current_org.id),
        "name": current_org.name,
        "organization_code": current_org.organization_code,
        "status": current_org.status.value
    }

@router.get("/rbac/super-admin")
async def check_super_admin(
    current_user: User = Depends(require_roles([UserRole.SUPER_ADMIN]))
):
    return {"status": "ok", "role": current_user.role.value}

@router.get("/rbac/admin-or-manager")
async def check_admin_or_manager(
    current_user: User = Depends(
        require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN, UserRole.SITE_MANAGER])
    )
):
    return {"status": "ok", "role": current_user.role.value}
