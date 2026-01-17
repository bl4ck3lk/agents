"""FastAPI Users configuration."""

import uuid

from fastapi_users import FastAPIUsers

from agents.api.auth.backend import auth_backend
from agents.api.auth.manager import get_user_manager
from agents.db.models import User

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

# Dependency shortcuts for protected routes
current_user = fastapi_users.current_user()
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
