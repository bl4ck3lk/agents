"""Model validation utilities."""

import logging

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_MODELS = [
    # OpenAI models
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4-turbo-preview",
    "gpt-3.5-turbo",
    # OpenRouter models (includes Anthropic, etc.)
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3.5-haiku",
    "google/gemini-pro",
    "meta-llama/llama-3.1-70b-instruct",
]


def get_allowed_models() -> list[str]:
    """
    Get list of allowed models from environment or defaults.

    Returns:
        List of allowed model identifiers.
    """
    import os

    env_models = os.getenv("ALLOWED_MODELS")
    if env_models:
        return [model.strip() for model in env_models.split(",") if model.strip()]
    return DEFAULT_ALLOWED_MODELS


def validate_model(model: str) -> tuple[bool, str | None]:
    """
    Validate that a model is in the allowed list.

    Args:
        model: Model identifier to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    allowed = get_allowed_models()

    if model not in allowed:
        logger.warning(f"Model validation failed: {model} not in allowed models")
        allowed_str = ", ".join(allowed[:10])
        if len(allowed) > 10:
            allowed_str += f", ... and {len(allowed) - 10} more"
        return (
            False,
            f"Model '{model}' is not allowed. Allowed models: {allowed_str}",
        )

    return True, None


def is_model_allowed(model: str) -> bool:
    """
    Check if a model is allowed without returning error message.

    Args:
        model: Model identifier to check.

    Returns:
        True if model is allowed, False otherwise.
    """
    is_valid, _ = validate_model(model)
    return is_valid
