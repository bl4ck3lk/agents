"""LLM client wrapper for OpenAI API."""

from typing import Any

from openai import (
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Fatal errors - don't retry, surface immediately
FATAL_ERRORS = (AuthenticationError, PermissionDeniedError, BadRequestError)

# Retryable errors - retry with exponential backoff + jitter
RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIError)


class FatalLLMError(Exception):
    """Wrapper for fatal LLM errors that should not be retried."""

    def __init__(self, original_error: Exception) -> None:
        self.original_error = original_error
        self.error_type = type(original_error).__name__
        super().__init__(f"{self.error_type}: {original_error}")


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        max_retries: int = 3,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _make_request(self, prompt: str, **kwargs: Any) -> str:
        """Make API request with retry logic for transient errors."""

        @retry(
            retry=retry_if_exception_type(RETRYABLE_ERRORS),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        )
        def _request() -> str:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                return response.choices[0].message.content or ""
            except FATAL_ERRORS as e:
                raise FatalLLMError(e) from e

        return _request()

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate completion for prompt."""
        return self._make_request(prompt, **kwargs)

    async def _make_request_async(self, prompt: str, **kwargs: Any) -> str:
        """Make async API request with retry logic."""
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type(RETRYABLE_ERRORS),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self.async_client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=kwargs.get("temperature", self.temperature),
                        max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    )
                    return response.choices[0].message.content or ""
                except FATAL_ERRORS as e:
                    raise FatalLLMError(e) from e

        raise RuntimeError("Async retry loop exited unexpectedly")

    async def complete_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate completion for prompt asynchronously."""
        return await self._make_request_async(prompt, **kwargs)
