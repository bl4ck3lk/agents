"""Admin routes for platform key and pricing management."""

from decimal import Decimal
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.api.auth import current_active_user
from agents.api.security import get_encryption
from agents.db.models import ModelPricing, PlatformAPIKey, SystemSettings, User
from agents.db.session import get_async_session

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_superuser(user: User = Depends(current_active_user)) -> User:
    """Dependency to require superuser access."""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# =============================================================================
# Platform API Keys
# =============================================================================


class PlatformKeyCreate(BaseModel):
    """Request to create a platform API key."""

    provider: str
    api_key: str  # Will be encrypted before storage
    name: Optional[str] = None
    base_url: Optional[str] = None


class PlatformKeyUpdate(BaseModel):
    """Request to update a platform API key."""

    api_key: Optional[str] = None
    name: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None


class PlatformKeyResponse(BaseModel):
    """Response for a platform API key."""

    id: str
    provider: str
    name: Optional[str]
    base_url: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/platform-keys", response_model=list[PlatformKeyResponse])
async def list_platform_keys(
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> list[PlatformKeyResponse]:
    """List all platform API keys."""
    result = await session.execute(
        select(PlatformAPIKey).order_by(PlatformAPIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        PlatformKeyResponse(
            id=key.id,
            provider=key.provider,
            name=key.name,
            base_url=key.base_url,
            is_active=key.is_active,
            created_at=key.created_at.isoformat(),
            updated_at=key.updated_at.isoformat(),
        )
        for key in keys
    ]


@router.post("/platform-keys", response_model=PlatformKeyResponse)
async def create_platform_key(
    body: PlatformKeyCreate,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> PlatformKeyResponse:
    """Create a new platform API key."""
    encryption = get_encryption()
    encrypted_key = encryption.encrypt(body.api_key)

    key = PlatformAPIKey(
        id=str(uuid4()),
        provider=body.provider,
        encrypted_key=encrypted_key,
        name=body.name,
        base_url=body.base_url,
    )
    session.add(key)
    await session.commit()
    await session.refresh(key)

    return PlatformKeyResponse(
        id=key.id,
        provider=key.provider,
        name=key.name,
        base_url=key.base_url,
        is_active=key.is_active,
        created_at=key.created_at.isoformat(),
        updated_at=key.updated_at.isoformat(),
    )


@router.patch("/platform-keys/{key_id}", response_model=PlatformKeyResponse)
async def update_platform_key(
    key_id: str,
    body: PlatformKeyUpdate,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> PlatformKeyResponse:
    """Update a platform API key."""
    result = await session.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.id == key_id)
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status_code=404, detail="Platform key not found")

    if body.api_key is not None:
        encryption = get_encryption()
        key.encrypted_key = encryption.encrypt(body.api_key)
    if body.name is not None:
        key.name = body.name
    if body.base_url is not None:
        key.base_url = body.base_url
    if body.is_active is not None:
        key.is_active = body.is_active

    await session.commit()
    await session.refresh(key)

    return PlatformKeyResponse(
        id=key.id,
        provider=key.provider,
        name=key.name,
        base_url=key.base_url,
        is_active=key.is_active,
        created_at=key.created_at.isoformat(),
        updated_at=key.updated_at.isoformat(),
    )


@router.delete("/platform-keys/{key_id}")
async def delete_platform_key(
    key_id: str,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Delete a platform API key."""
    result = await session.execute(
        select(PlatformAPIKey).where(PlatformAPIKey.id == key_id)
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status_code=404, detail="Platform key not found")

    await session.delete(key)
    await session.commit()

    return {"success": True}


# =============================================================================
# Model Pricing
# =============================================================================


class PricingCreate(BaseModel):
    """Request to create model pricing."""

    model_pattern: str
    provider: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    markup_percentage: Decimal = Decimal("20")


class PricingUpdate(BaseModel):
    """Request to update model pricing."""

    model_pattern: Optional[str] = None
    provider: Optional[str] = None
    input_cost_per_million: Optional[Decimal] = None
    output_cost_per_million: Optional[Decimal] = None
    markup_percentage: Optional[Decimal] = None


class PricingResponse(BaseModel):
    """Response for model pricing."""

    id: str
    model_pattern: str
    provider: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    markup_percentage: Decimal
    effective_from: str
    effective_to: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.get("/model-pricing", response_model=list[PricingResponse])
async def list_model_pricing(
    active_only: bool = True,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> list[PricingResponse]:
    """List all model pricing entries."""
    query = select(ModelPricing).order_by(
        ModelPricing.provider, ModelPricing.model_pattern
    )
    if active_only:
        query = query.where(ModelPricing.effective_to.is_(None))

    result = await session.execute(query)
    pricing_list = result.scalars().all()

    return [
        PricingResponse(
            id=p.id,
            model_pattern=p.model_pattern,
            provider=p.provider,
            input_cost_per_million=p.input_cost_per_million,
            output_cost_per_million=p.output_cost_per_million,
            markup_percentage=p.markup_percentage,
            effective_from=p.effective_from.isoformat(),
            effective_to=p.effective_to.isoformat() if p.effective_to else None,
            created_at=p.created_at.isoformat(),
        )
        for p in pricing_list
    ]


@router.post("/model-pricing", response_model=PricingResponse)
async def create_model_pricing(
    body: PricingCreate,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> PricingResponse:
    """Create a new model pricing entry."""
    pricing = ModelPricing(
        id=str(uuid4()),
        model_pattern=body.model_pattern,
        provider=body.provider,
        input_cost_per_million=body.input_cost_per_million,
        output_cost_per_million=body.output_cost_per_million,
        markup_percentage=body.markup_percentage,
    )
    session.add(pricing)
    await session.commit()
    await session.refresh(pricing)

    return PricingResponse(
        id=pricing.id,
        model_pattern=pricing.model_pattern,
        provider=pricing.provider,
        input_cost_per_million=pricing.input_cost_per_million,
        output_cost_per_million=pricing.output_cost_per_million,
        markup_percentage=pricing.markup_percentage,
        effective_from=pricing.effective_from.isoformat(),
        effective_to=None,
        created_at=pricing.created_at.isoformat(),
    )


@router.patch("/model-pricing/{pricing_id}", response_model=PricingResponse)
async def update_model_pricing(
    pricing_id: str,
    body: PricingUpdate,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> PricingResponse:
    """Update model pricing."""
    result = await session.execute(
        select(ModelPricing).where(ModelPricing.id == pricing_id)
    )
    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing not found")

    if body.model_pattern is not None:
        pricing.model_pattern = body.model_pattern
    if body.provider is not None:
        pricing.provider = body.provider
    if body.input_cost_per_million is not None:
        pricing.input_cost_per_million = body.input_cost_per_million
    if body.output_cost_per_million is not None:
        pricing.output_cost_per_million = body.output_cost_per_million
    if body.markup_percentage is not None:
        pricing.markup_percentage = body.markup_percentage

    await session.commit()
    await session.refresh(pricing)

    return PricingResponse(
        id=pricing.id,
        model_pattern=pricing.model_pattern,
        provider=pricing.provider,
        input_cost_per_million=pricing.input_cost_per_million,
        output_cost_per_million=pricing.output_cost_per_million,
        markup_percentage=pricing.markup_percentage,
        effective_from=pricing.effective_from.isoformat(),
        effective_to=pricing.effective_to.isoformat() if pricing.effective_to else None,
        created_at=pricing.created_at.isoformat(),
    )


@router.delete("/model-pricing/{pricing_id}")
async def delete_model_pricing(
    pricing_id: str,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    """Delete model pricing entry."""
    result = await session.execute(
        select(ModelPricing).where(ModelPricing.id == pricing_id)
    )
    pricing = result.scalar_one_or_none()

    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing not found")

    await session.delete(pricing)
    await session.commit()

    return {"success": True}


# =============================================================================
# User Platform Access
# =============================================================================


class UserPlatformAccessUpdate(BaseModel):
    """Request to update user platform access."""

    can_use_platform_key: Optional[bool] = None
    monthly_usage_limit_usd: Optional[Decimal] = None


class UserPlatformAccessResponse(BaseModel):
    """Response for user platform access."""

    id: str
    email: str
    can_use_platform_key: bool
    monthly_usage_limit_usd: Optional[Decimal]


@router.patch(
    "/users/{user_id}/platform-access", response_model=UserPlatformAccessResponse
)
async def update_user_platform_access(
    user_id: str,
    body: UserPlatformAccessUpdate,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> UserPlatformAccessResponse:
    """Update user's platform key access."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.can_use_platform_key is not None:
        user.can_use_platform_key = body.can_use_platform_key
    if body.monthly_usage_limit_usd is not None:
        user.monthly_usage_limit_usd = body.monthly_usage_limit_usd

    await session.commit()
    await session.refresh(user)

    return UserPlatformAccessResponse(
        id=str(user.id),
        email=user.email,
        can_use_platform_key=user.can_use_platform_key,
        monthly_usage_limit_usd=user.monthly_usage_limit_usd,
    )


# =============================================================================
# System Settings
# =============================================================================


class SettingResponse(BaseModel):
    """Response for a system setting."""

    key: str
    value: str
    updated_at: str


class SettingUpdate(BaseModel):
    """Request to update a system setting."""

    value: str


@router.get("/settings/{key}", response_model=SettingResponse)
async def get_setting(
    key: str,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> SettingResponse:
    """Get a system setting by key."""
    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    return SettingResponse(
        key=setting.key,
        value=setting.value,
        updated_at=setting.updated_at.isoformat(),
    )


@router.put("/settings/{key}", response_model=SettingResponse)
async def update_setting(
    key: str,
    body: SettingUpdate,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> SettingResponse:
    """Update or create a system setting."""
    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = body.value
    else:
        setting = SystemSettings(key=key, value=body.value)
        session.add(setting)

    await session.commit()
    await session.refresh(setting)

    return SettingResponse(
        key=setting.key,
        value=setting.value,
        updated_at=setting.updated_at.isoformat(),
    )


@router.get("/settings", response_model=list[SettingResponse])
async def list_settings(
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_async_session),
) -> list[SettingResponse]:
    """List all system settings."""
    result = await session.execute(
        select(SystemSettings).order_by(SystemSettings.key)
    )
    settings = result.scalars().all()

    return [
        SettingResponse(
            key=s.key,
            value=s.value,
            updated_at=s.updated_at.isoformat(),
        )
        for s in settings
    ]
