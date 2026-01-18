"""LLM client wrapper for OpenAI API."""

import os
from dataclasses import dataclass
from typing import Any

from agents.utils.config import DEFAULT_MAX_RETRIES, DEFAULT_MAX_TOKENS

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
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Fatal errors - don't retry, surface immediately
FATAL_ERRORS = (AuthenticationError, PermissionDeniedError, BadRequestError)

# Retryable errors - retry with exponential backoff + jitter
RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIError)


@dataclass
class UsageMetadata:
    """Token usage from LLM response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str | None = None


@dataclass
class LLMResponse:
    """LLM response with content and usage metadata."""

    content: str
    usage: UsageMetadata | None = None


class FatalLLMError(Exception):
    """Wrapper for fatal LLM errors that should not be retried."""

    def __init__(self, original_error: Exception) -> None:
        self.original_error = original_error
        self.error_type = type(original_error).__name__
        super().__init__(f"{self.error_type}: {original_error}")


DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    """You are a data processing assistant. Your task is to process the input and return ONLY valid JSON output.

CRITICAL RULES:
1. Return ONLY valid JSON - no markdown, no explanations, no extra text
2. Do NOT wrap the response in ```json``` code blocks
3. Do NOT include any text before or after the JSON
4. The JSON must be parseable by a machine

If the task asks for multiple values, return them as a JSON object with descriptive keys.""",
)


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        system_prompt: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _build_messages(self, prompt: str) -> list[dict[str, str]]:
        """Build messages array with system prompt."""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _make_request(self, prompt: str, **kwargs: Any) -> str:
        """Make API request with retry logic for transient errors."""

        @retry(
            retry=(
                retry_if_exception_type(RETRYABLE_ERRORS)
                & retry_if_not_exception_type(FATAL_ERRORS)
            ),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        )
        def _request() -> str:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt),
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            return response.choices[0].message.content or ""

        return _request()

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """Generate completion for prompt.

        Raises:
            FatalLLMError: For authentication/permission errors (no retry).
        """
        try:
            return self._make_request(prompt, **kwargs)
        except FATAL_ERRORS as e:
            raise FatalLLMError(e) from e

    def _make_request_with_usage(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Make API request and return response with usage metadata."""

        @retry(
            retry=(
                retry_if_exception_type(RETRYABLE_ERRORS)
                & retry_if_not_exception_type(FATAL_ERRORS)
            ),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        )
        def _request() -> LLMResponse:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(prompt),
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            content = response.choices[0].message.content or ""
            usage = None
            if response.usage:
                usage = UsageMetadata(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                    model=response.model,
                )
            return LLMResponse(content=content, usage=usage)

        return _request()

    def complete_with_usage(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate completion for prompt and return with usage metadata.

        Returns:
            LLMResponse with content and token usage.

        Raises:
            FatalLLMError: For authentication/permission errors (no retry).
        """
        try:
            return self._make_request_with_usage(prompt, **kwargs)
        except FATAL_ERRORS as e:
            raise FatalLLMError(e) from e

    async def _make_request_async(self, prompt: str, **kwargs: Any) -> str:
        """Make async API request with retry logic."""
        async for attempt in AsyncRetrying(
            retry=(
                retry_if_exception_type(RETRYABLE_ERRORS)
                & retry_if_not_exception_type(FATAL_ERRORS)
            ),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        ):
            with attempt:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=self._build_messages(prompt),
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                return response.choices[0].message.content or ""

        raise RuntimeError("Async retry loop exited unexpectedly")

    async def complete_async(self, prompt: str, **kwargs: Any) -> str:
        """Generate completion for prompt asynchronously.

        Raises:
            FatalLLMError: For authentication/permission errors (no retry).
        """
        try:
            return await self._make_request_async(prompt, **kwargs)
        except FATAL_ERRORS as e:
            raise FatalLLMError(e) from e

    async def _make_request_with_usage_async(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Make async API request and return response with usage metadata."""
        async for attempt in AsyncRetrying(
            retry=(
                retry_if_exception_type(RETRYABLE_ERRORS)
                & retry_if_not_exception_type(FATAL_ERRORS)
            ),
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
            reraise=True,
        ):
            with attempt:
                response = await self.async_client.chat.completions.create(
                    model=self.model,
                    messages=self._build_messages(prompt),
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                content = response.choices[0].message.content or ""
                usage = None
                if response.usage:
                    usage = UsageMetadata(
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                        model=response.model,
                    )
                return LLMResponse(content=content, usage=usage)

        raise RuntimeError("Async retry loop exited unexpectedly")

    async def complete_with_usage_async(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate completion for prompt asynchronously with usage metadata.

        Returns:
            LLMResponse with content and token usage.

        Raises:
            FatalLLMError: For authentication/permission errors (no retry).
        """
        try:
            return await self._make_request_with_usage_async(prompt, **kwargs)
        except FATAL_ERRORS as e:
            raise FatalLLMError(e) from e
