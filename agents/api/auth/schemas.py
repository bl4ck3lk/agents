"""Pydantic schemas for authentication."""

import uuid

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    """Schema for reading user data."""

    name: str | None = None
    avatar_url: str | None = None
    can_use_platform_key: bool = False


class UserCreate(schemas.BaseUserCreate):
    """Schema for creating a user."""

    name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating a user."""

    name: str | None = None
    avatar_url: str | None = None
