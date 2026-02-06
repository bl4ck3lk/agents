"""User manager for fastapi-users."""

import logging
import uuid

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin

from agents.api.auth.config import auth_config
from agents.db.models import User
from agents.db.session import async_session_maker

logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """User manager for handling user operations."""

    reset_password_token_secret = auth_config.secret_key
    verification_token_secret = auth_config.secret_key

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """Called after user registration."""
        logger.info("User %s has registered.", user.id)

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after forgot password request."""
        logger.info("User %s has requested password reset.", user.id)
        if auth_config.resend_api_key:
            reset_url = f"{auth_config.reset_password_url}?token={token}"
            logger.info("Password reset URL generated for user %s", user.id)

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """Called after email verification request."""
        logger.info("User %s has requested email verification.", user.id)
        if auth_config.resend_api_key:
            verify_url = f"{auth_config.verify_email_url}?token={token}"
            logger.info("Verification URL generated for user %s", user.id)


async def get_user_db():
    """Get user database adapter."""
    from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

    async with async_session_maker() as session:
        yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Dependency for getting user manager."""
    yield UserManager(user_db)
