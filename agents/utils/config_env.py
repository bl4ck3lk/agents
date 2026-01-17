"""Configuration utilities for the application."""

import os


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Get boolean environment variable.

    Args:
        key: Environment variable name.
        default: Default value if not set.

    Returns:
        Boolean value.
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def get_env_int(key: str, default: int = 0) -> int:
    """
    Get integer environment variable.

    Args:
        key: Environment variable name.
        default: Default value if not set.

    Returns:
        Integer value.
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_list(key: str, default: list[str] | None = None) -> list[str]:
    """
    Get list environment variable (comma-separated).

    Args:
        key: Environment variable name.
        default: Default value if not set.

    Returns:
        List of string values.
    """
    value = os.getenv(key)
    if value is None:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_required_env_vars(*keys: str) -> dict[str, str]:
    """
    Validate that required environment variables are set.

    Args:
        *keys: Environment variable names to check.

    Returns:
        Dictionary of present environment variables.

    Raises:
        ValueError: If any required variable is missing or has placeholder value.
    """
    missing = []
    placeholders = []
    env_vars = {}

    PLACEHOLDERS = (
        "your-secret-key-change-in-production",
        "your-32-byte-encryption-key-here",
        "minioadmin",
        "change-me",
    )

    for key in keys:
        value = os.getenv(key)
        if value is None:
            missing.append(key)
        elif value.lower() in PLACEHOLDERS:
            placeholders.append(key)
        else:
            env_vars[key] = value

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    if placeholders:
        raise ValueError(
            f"Placeholder values detected in environment variables (change before production): {', '.join(placeholders)}"
        )

    return env_vars
