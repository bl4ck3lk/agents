"""User manager for fastapi-users."""

import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin

from agents.api.auth.config import auth_config
from agents.db.models import User
from agents.db.session import async_session_maker


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """User manager for handling user operations."""

    reset_password_token_secret = auth_config.secret_key
    verification_token_secret = auth_config.secret_key

    async def on_after_register(self, user: User, request: Optional[Request] = None) -> None:
        """Called after user registration."""
        print(f"User {user.id} has registered.")
        # TODO: Send welcome email if email service is configured

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        """Called after forgot password request."""
        print(f"User {user.id} has requested password reset.")
        # TODO: Send password reset email
        # reset_url = f"{auth_config.reset_password_url}?token={token}"

    async def on_after_request_verify(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        """Called after email verification request."""
        print(f"User {user.id} has requested email verification.")
        # TODO: Send verification email
        # verify_url = f"{auth_config.verify_email_url}?token={token}"


async def get_user_db():
    """Get user database adapter."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
    from sqlalchemy.ext.asyncio import AsyncSession

    async with async_session_maker() as session:
        yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency for getting user manager."""
    yield UserManager(user_db)
