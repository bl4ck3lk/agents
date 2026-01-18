"""Usage tracking and billing routes."""

from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import Integer, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from agents.api.auth import current_active_user
from agents.db.models import Usage, User
from agents.db.session import get_async_session

router = APIRouter(prefix="/usage", tags=["Usage"])


class UsageRecord(BaseModel):
    """A single usage record."""

    id: str
    job_id: str
    model: str | None
    provider: str | None
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    raw_cost_usd: Decimal
    markup_usd: Decimal
    used_platform_key: bool
    created_at: str


class UsageListResponse(BaseModel):
    """Response for listing usage records."""

    records: list[UsageRecord]
    total: int
    offset: int
    limit: int


class ModelBreakdown(BaseModel):
    """Usage breakdown by model."""

    model: str
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    count: int


class DailyTotal(BaseModel):
    """Daily usage total."""

    date: str
    tokens_input: int
    tokens_output: int
    cost_usd: Decimal
    count: int


class UsageSummary(BaseModel):
    """Aggregated usage summary."""

    total_cost_usd: Decimal
    total_raw_cost_usd: Decimal
    total_markup_usd: Decimal
    total_tokens_input: int
    total_tokens_output: int
    total_jobs: int
    platform_key_jobs: int
    by_model: list[ModelBreakdown]
    daily_totals: list[DailyTotal]


@router.get("", response_model=UsageListResponse)
async def list_usage(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    start_date: str | None = None,
    end_date: str | None = None,
    model: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> UsageListResponse:
    """List usage records for the current user."""
    query = select(Usage).where(Usage.user_id == str(user.id))

    # Apply filters
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.where(Usage.created_at >= start)
        except ValueError:
            pass  # Invalid date format - ignore filter

    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.where(Usage.created_at <= end)
        except ValueError:
            pass  # Invalid date format - ignore filter

    if model:
        query = query.where(Usage.model == model)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar() or 0

    # Get paginated results
    query = query.order_by(Usage.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    records = result.scalars().all()

    return UsageListResponse(
        records=[
            UsageRecord(
                id=r.id,
                job_id=r.job_id,
                model=r.model,
                provider=r.provider,
                tokens_input=r.tokens_input,
                tokens_output=r.tokens_output,
                cost_usd=r.cost_usd,
                raw_cost_usd=r.raw_cost_usd,
                markup_usd=r.markup_usd,
                used_platform_key=r.used_platform_key,
                created_at=r.created_at.isoformat(),
            )
            for r in records
        ],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> UsageSummary:
    """Get aggregated usage summary for the current user."""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Base query for the time period
    base_filter = [
        Usage.user_id == str(user.id),
        Usage.created_at >= start_date,
    ]

    # Get totals
    totals_result = await session.execute(
        select(
            func.sum(Usage.cost_usd).label("total_cost"),
            func.sum(Usage.raw_cost_usd).label("total_raw_cost"),
            func.sum(Usage.markup_usd).label("total_markup"),
            func.sum(Usage.tokens_input).label("total_input"),
            func.sum(Usage.tokens_output).label("total_output"),
            func.count(Usage.id).label("total_jobs"),
            func.sum(func.cast(Usage.used_platform_key, Integer)).label("platform_jobs"),
        ).where(*base_filter)
    )
    totals = totals_result.one()

    # Get breakdown by model
    model_result = await session.execute(
        select(
            Usage.model,
            func.sum(Usage.tokens_input).label("tokens_input"),
            func.sum(Usage.tokens_output).label("tokens_output"),
            func.sum(Usage.cost_usd).label("cost_usd"),
            func.count(Usage.id).label("count"),
        )
        .where(*base_filter)
        .group_by(Usage.model)
        .order_by(func.sum(Usage.cost_usd).desc())
    )
    by_model = [
        ModelBreakdown(
            model=row.model or "unknown",
            tokens_input=int(row.tokens_input or 0),
            tokens_output=int(row.tokens_output or 0),
            cost_usd=row.cost_usd or Decimal("0"),
            count=int(row.count or 0),
        )
        for row in model_result
    ]

    # Get daily totals
    daily_result = await session.execute(
        text("""
            SELECT
                DATE(created_at) as date,
                SUM(tokens_input) as tokens_input,
                SUM(tokens_output) as tokens_output,
                SUM(cost_usd) as cost_usd,
                COUNT(*) as count
            FROM usage
            WHERE user_id = :user_id AND created_at >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
        """),
        {"user_id": str(user.id), "start_date": start_date},
    )
    daily_totals = [
        DailyTotal(
            date=str(row.date),
            tokens_input=int(row.tokens_input or 0),
            tokens_output=int(row.tokens_output or 0),
            cost_usd=row.cost_usd or Decimal("0"),
            count=int(row.count or 0),
        )
        for row in daily_result
    ]

    return UsageSummary(
        total_cost_usd=totals.total_cost or Decimal("0"),
        total_raw_cost_usd=totals.total_raw_cost or Decimal("0"),
        total_markup_usd=totals.total_markup or Decimal("0"),
        total_tokens_input=totals.total_input or 0,
        total_tokens_output=totals.total_output or 0,
        total_jobs=totals.total_jobs or 0,
        platform_key_jobs=totals.platform_jobs or 0,
        by_model=by_model,
        daily_totals=daily_totals,
    )


@router.get("/export")
async def export_usage(
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> StreamingResponse:
    """Export usage records as CSV."""
    query = select(Usage).where(Usage.user_id == str(user.id))

    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
            query = query.where(Usage.created_at >= start)
        except ValueError:
            pass  # Invalid date format - ignore filter

    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
            query = query.where(Usage.created_at <= end)
        except ValueError:
            pass  # Invalid date format - ignore filter

    query = query.order_by(Usage.created_at.desc())
    result = await session.execute(query)
    records = result.scalars().all()

    def generate_csv() -> Iterator[str]:
        # Header
        yield "id,job_id,model,provider,tokens_input,tokens_output,cost_usd,raw_cost_usd,markup_usd,used_platform_key,created_at\n"

        # Rows
        for r in records:
            yield f"{r.id},{r.job_id},{r.model or ''},{r.provider or ''},{r.tokens_input},{r.tokens_output},{r.cost_usd},{r.raw_cost_usd},{r.markup_usd},{r.used_platform_key},{r.created_at.isoformat()}\n"

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=usage_export.csv"},
    )
