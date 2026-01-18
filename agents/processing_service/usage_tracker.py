"""Usage tracking and cost calculation for job processing."""

import fnmatch
import logging
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select, text

from agents.db.models import ModelPricing
from agents.db.session import async_session_maker

logger = logging.getLogger(__name__)


class UsageTracker:
    """Tracks token usage and calculates costs for jobs."""

    async def get_model_pricing(self, model: str, provider: str) -> ModelPricing | None:
        """Get pricing for a model using pattern matching.

        Args:
            model: The model name (e.g., 'gpt-4o-mini')
            provider: The provider (e.g., 'openai', 'openrouter')

        Returns:
            ModelPricing if found, None otherwise
        """
        async with async_session_maker() as session:
            # Get all active pricing entries for the provider
            result = await session.execute(
                select(ModelPricing).where(
                    ModelPricing.provider == provider,
                    ModelPricing.effective_to.is_(None),  # Active entries only
                )
            )
            pricing_entries = result.scalars().all()

            # Try pattern matching (supports * wildcards like 'gpt-4o*')
            for pricing in pricing_entries:
                # Convert SQL LIKE pattern to fnmatch pattern
                pattern = pricing.model_pattern.replace("%", "*")
                if fnmatch.fnmatch(model, pattern):
                    return pricing

            # No match found
            logger.warning(
                "No pricing found for model=%s, provider=%s",
                model,
                provider,
            )
            return None

    def calculate_cost(
        self,
        tokens_input: int,
        tokens_output: int,
        pricing: ModelPricing | None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate raw cost, markup, and total cost.

        Args:
            tokens_input: Number of input/prompt tokens
            tokens_output: Number of output/completion tokens
            pricing: ModelPricing entry (or None for zero cost)

        Returns:
            Tuple of (raw_cost, markup, total_cost) in USD
        """
        if pricing is None:
            return Decimal("0"), Decimal("0"), Decimal("0")

        # Calculate raw cost
        input_cost = Decimal(tokens_input) * pricing.input_cost_per_million / Decimal("1000000")
        output_cost = Decimal(tokens_output) * pricing.output_cost_per_million / Decimal("1000000")
        raw_cost = input_cost + output_cost

        # Apply markup
        markup = raw_cost * (pricing.markup_percentage / Decimal("100"))
        total_cost = raw_cost + markup

        return raw_cost, markup, total_cost

    async def record_usage(
        self,
        job_id: str,
        user_id: str,
        model: str,
        provider: str,
        tokens_input: int,
        tokens_output: int,
        used_platform_key: bool,
    ) -> None:
        """Record usage in the database with cost calculation.

        Args:
            job_id: The web job ID
            user_id: The user ID
            model: The LLM model used
            provider: The API provider
            tokens_input: Number of input tokens
            tokens_output: Number of output tokens
            used_platform_key: Whether platform API key was used
        """
        # Get pricing and calculate cost
        pricing = await self.get_model_pricing(model, provider)
        raw_cost, markup, total_cost = self.calculate_cost(tokens_input, tokens_output, pricing)

        # Insert usage record
        async with async_session_maker() as session:
            await session.execute(
                text("""
                    INSERT INTO usage (
                        id, user_id, job_id, tokens_input, tokens_output,
                        cost_usd, model, provider, used_platform_key,
                        raw_cost_usd, markup_usd
                    ) VALUES (
                        :id, :user_id, :job_id, :tokens_input, :tokens_output,
                        :cost_usd, :model, :provider, :used_platform_key,
                        :raw_cost_usd, :markup_usd
                    )
                """),
                {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "job_id": job_id,
                    "tokens_input": tokens_input,
                    "tokens_output": tokens_output,
                    "cost_usd": total_cost,
                    "model": model,
                    "provider": provider,
                    "used_platform_key": used_platform_key,
                    "raw_cost_usd": raw_cost,
                    "markup_usd": markup,
                },
            )
            await session.commit()

        logger.info(
            f"Recorded usage for job {job_id}: "
            f"{tokens_input} input + {tokens_output} output tokens, "
            f"cost=${total_cost:.6f} (raw=${raw_cost:.6f} + markup=${markup:.6f})"
        )


# Singleton instance
_usage_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    """Get or create the usage tracker singleton."""
    global _usage_tracker
    if _usage_tracker is None:
        _usage_tracker = UsageTracker()
    return _usage_tracker
