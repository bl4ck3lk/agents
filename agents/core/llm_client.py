"""LLM client wrapper for OpenAI API."""

import asyncio
from typing import Any

from openai import APIError, AsyncOpenAI, OpenAI, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            api_key: API key for authentication.
            model: Model name to use.
            base_url: Optional base URL for API endpoint.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            max_retries: Maximum retry attempts for transient errors.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _make_request(self, prompt: str, **kwargs: Any) -> str:
        """Make API request with retry logic."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        return response.choices[0].message.content or ""

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.
        """
        return self._make_request(prompt, **kwargs)

    async def complete_async(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt asynchronously.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.
        """
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((RateLimitError, APIError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
        ):
            with attempt:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )

                return response.choices[0].message.content or ""
