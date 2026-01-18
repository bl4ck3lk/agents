"""API key management routes."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.api.auth import current_active_user
from agents.api.security import get_encryption
from agents.db.models import APIKey, User
from agents.db.session import get_async_session

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class APIKeyCreate(BaseModel):
    """Request to create an API key."""

    provider: str  # 'openai', 'anthropic', etc.
    api_key: str  # The actual key to encrypt
    name: str | None = None  # User-friendly label


class APIKeyResponse(BaseModel):
    """Response for an API key (masked)."""

    id: str
    provider: str
    name: str | None
    masked_key: str
    created_at: str

    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """Response for listing API keys."""

    keys: list[APIKeyResponse]


@router.post("", response_model=APIKeyResponse)
async def create_api_key(
    body: APIKeyCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIKeyResponse:
    """Store an encrypted API key."""
    encryption = get_encryption()

    # Encrypt the API key
    encrypted = encryption.encrypt(body.api_key)
    masked = encryption.mask_key(body.api_key)

    # Create the record
    api_key = APIKey(
        id=str(uuid4()),
        user_id=str(user.id),
        provider=body.provider,
        encrypted_key=encrypted,
        name=body.name,
    )

    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return APIKeyResponse(
        id=api_key.id,
        provider=api_key.provider,
        name=api_key.name,
        masked_key=masked,
        created_at=api_key.created_at.isoformat(),
    )


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> APIKeyListResponse:
    """List all API keys for the current user (masked)."""
    result = await session.execute(
        select(APIKey).where(APIKey.user_id == str(user.id)).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    encryption = get_encryption()
    response_keys = []

    for key in keys:
        # Decrypt to get masked version
        try:
            decrypted = encryption.decrypt(key.encrypted_key)
            masked = encryption.mask_key(decrypted)
        except Exception:
            masked = "****"

        response_keys.append(
            APIKeyResponse(
                id=key.id,
                provider=key.provider,
                name=key.name,
                masked_key=masked,
                created_at=key.created_at.isoformat(),
            )
        )

    return APIKeyListResponse(keys=response_keys)


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Delete an API key."""
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == str(user.id))
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await session.delete(api_key)
    await session.commit()

    return {"success": True}


async def get_decrypted_api_key(
    user_id: str,
    provider: str,
    session: AsyncSession,
) -> str | None:
    """Get decrypted API key for a user and provider.

    This is an internal utility function, not an endpoint.
    """
    result = await session.execute(
        select(APIKey)
        .where(
            APIKey.user_id == user_id,
            APIKey.provider == provider,
        )
        .order_by(APIKey.created_at.desc())
        .limit(1)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        return None

    encryption = get_encryption()
    return encryption.decrypt(api_key.encrypted_key)
