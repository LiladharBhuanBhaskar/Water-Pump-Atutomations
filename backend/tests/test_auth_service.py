import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.base import Base
from app.db.session import sync_engine, get_async_session
from app.models.user import User, UserRole
from app.schemas.auth import UserRegistrationRequest, LoginRequest
from app.services.auth import (
    register_user, 
    authenticate_user, 
    UserAlreadyExistsException, 
    InvalidCredentialsException,
    InactiveUserException
)

@pytest.fixture(scope="module", autouse=True)
def setup_tables():
    """Create tables before running tests and clean up after."""
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)

@pytest.mark.asyncio
async def test_register_user_success():
    req = UserRegistrationRequest(
        name="New User",
        email="newuser@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        user = await register_user(session, req)
        
        assert user.id is not None
        assert user.name == "New User"
        assert user.email == "newuser@example.com"
        assert user.role == UserRole.VIEWER
        assert user.is_active is True
        assert user.password_hash != "securepassword123"

@pytest.mark.asyncio
async def test_register_user_duplicate_email():
    req1 = UserRegistrationRequest(
        name="User One",
        email="duplicate@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        await register_user(session, req1)
        
        req2 = UserRegistrationRequest(
            name="User Two",
            email="DUPLICATE@example.com", # different case
            password="anotherpassword"
        )
        with pytest.raises(UserAlreadyExistsException):
            await register_user(session, req2)

@pytest.mark.asyncio
async def test_authenticate_user_success():
    req = UserRegistrationRequest(
        name="Login User",
        email="login@example.com",
        password="securepassword123"
    )
    login_req = LoginRequest(
        email="login@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        await register_user(session, req)
        
        token_resp = await authenticate_user(session, login_req)
        assert token_resp.access_token is not None
        assert token_resp.token_type == "bearer"

@pytest.mark.asyncio
async def test_authenticate_user_invalid_password():
    login_req = LoginRequest(
        email="login@example.com",
        password="wrongpassword"
    )
    async with get_async_session() as session:
        with pytest.raises(InvalidCredentialsException):
            await authenticate_user(session, login_req)

@pytest.mark.asyncio
async def test_authenticate_user_unknown_email():
    login_req = LoginRequest(
        email="unknown@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        with pytest.raises(InvalidCredentialsException):
            await authenticate_user(session, login_req)

@pytest.mark.asyncio
async def test_authenticate_user_inactive():
    req = UserRegistrationRequest(
        name="Inactive User",
        email="inactive@example.com",
        password="securepassword123"
    )
    async with get_async_session() as session:
        user = await register_user(session, req)
        user.is_active = False
        await session.commit()
        
        login_req = LoginRequest(
            email="inactive@example.com",
            password="securepassword123"
        )
        with pytest.raises(InactiveUserException):
            await authenticate_user(session, login_req)
