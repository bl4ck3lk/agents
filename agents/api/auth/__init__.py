"""Authentication module for agents web app."""

from agents.api.auth.backend import auth_backend
from agents.api.auth.config import auth_config
from agents.api.auth.manager import get_user_manager
from agents.api.auth.users import (
    current_active_user,
    current_superuser,
    current_user,
    fastapi_users,
)

__all__ = [
    "auth_backend",
    "auth_config",
    "current_active_user",
    "current_superuser",
    "current_user",
    "fastapi_users",
    "get_user_manager",
]
