"""LLM client wrapper for OpenAI API."""

from typing import Any

from openai import OpenAI


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            api_key: API key for authentication.
            model: Model name to use.
            base_url: Optional base URL for API endpoint.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        return response.choices[0].message.content or ""
