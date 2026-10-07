import pytest
from fastapi import HTTPException, status
from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import sync_engine, get_async_session
from app.models.user import User, UserRole
from app.services.auth import register_user
from app.schemas.auth import UserRegistrationRequest
from app.core.security import create_access_token

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.mark.asyncio
async def test_get_current_user_success():
    req = UserRegistrationRequest(
        name="Dep User",
        email="dep@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        user = await register_user(session, req)
        token = create_access_token(subject=str(user.id))
        
        current_user = await get_current_user(token=token, session=session)
        assert current_user.id == user.id
        assert current_user.email == "dep@example.com"

@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    async with get_async_session() as session:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token="invalid_token", session=session)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_get_current_user_not_found():
    # token with an ID that doesn't exist
    import uuid
    token = create_access_token(subject=str(uuid.uuid4()))
    async with get_async_session() as session:
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token, session=session)
        assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.asyncio
async def test_get_current_user_inactive():
    req = UserRegistrationRequest(
        name="Inactive Dep User",
        email="inactivedep@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        user = await register_user(session, req)
        user.is_active = False
        await session.commit()
        
        token = create_access_token(subject=str(user.id))
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token, session=session)
        assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_roles_success():
    from app.api.deps import require_roles
    checker = require_roles([UserRole.SUPER_ADMIN, UserRole.ORGANIZATION_ADMIN])
    
    # Authorized
    user = User(role=UserRole.SUPER_ADMIN)
    result = await checker(user)
    assert result == user
    
    user2 = User(role=UserRole.ORGANIZATION_ADMIN)
    result2 = await checker(user2)
    assert result2 == user2

@pytest.mark.asyncio
async def test_require_roles_failure():
    from app.api.deps import require_roles
    checker = require_roles([UserRole.SUPER_ADMIN])
    
    # Unauthorized
    user = User(role=UserRole.VIEWER)
    with pytest.raises(HTTPException) as exc:
        await checker(user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc.value.detail == "Not enough permissions"

