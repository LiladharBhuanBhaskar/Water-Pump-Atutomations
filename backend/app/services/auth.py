import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserRole
from app.schemas.auth import UserRegistrationRequest, LoginRequest, TokenResponse
from app.core.security import get_password_hash, verify_password, create_access_token

class UserAlreadyExistsException(Exception):
    pass

class InvalidCredentialsException(Exception):
    pass

class InactiveUserException(Exception):
    pass


async def register_user(session: AsyncSession, req: UserRegistrationRequest) -> User:
    # Normalize email
    normalized_email = req.email.lower().strip()

    # Check for existing email
    stmt = select(User).where(User.email == normalized_email)
    result = await session.execute(stmt)
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise UserAlreadyExistsException("A user with this email already exists.")

    # Create user
    new_user = User(
        id=uuid.uuid4(),
        name=req.name.strip(),
        email=normalized_email,
        password_hash=get_password_hash(req.password),
        role=UserRole.VIEWER,
        is_active=True
    )
    
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

async def authenticate_user(session: AsyncSession, req: LoginRequest) -> TokenResponse:
    normalized_email = req.email.lower().strip()
    
    stmt = select(User).where(User.email == normalized_email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise InvalidCredentialsException("Invalid email or password")
        
    if not verify_password(req.password, user.password_hash):
        raise InvalidCredentialsException("Invalid email or password")
        
    if not user.is_active:
        raise InactiveUserException("User is inactive")
        
    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token, token_type="bearer")
