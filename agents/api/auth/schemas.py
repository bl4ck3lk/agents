"""Pydantic schemas for authentication."""

import uuid
from typing import Optional

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Schema for reading user data."""

    name: Optional[str] = None
    avatar_url: Optional[str] = None
    can_use_platform_key: bool = False


class UserCreate(schemas.BaseUserCreate):
    """Schema for creating a user."""

    name: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating a user."""

    name: Optional[str] = None
    avatar_url: Optional[str] = None
