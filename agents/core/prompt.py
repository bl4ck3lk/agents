"""Prompt template for LLM requests."""

import re
from string import Formatter


class PromptTemplate:
    """Template for rendering prompts with data."""

    PROMPT_INJECTION_PATTERNS = [
        r"(?i)(ignore|disregard|forget|above|previous|instructions)",
        r"(?i)(return|reveal|show|display|print|output).*system.*prompt",
        r"(?i)(new.*role|role.*play|act.*as|you.*are.*now)",
        r"(?i)(\bexec\b|\brun\b|\beval\b|execute|execute)",
        r"(?i)(\|\|\|.*\|\||<\|.*\|>|<<.*>>)",
    ]

    def __init__(self, template: str) -> None:
        """
        Initialize prompt template.

        Args:
            template: Template string with {field} placeholders.
        """
        self.template = template
        self._formatter = Formatter()

    def _sanitize_value(self, value: str) -> str:
        """
        Sanitize a single value to prevent prompt injection.

        Args:
            value: The value to sanitize.

        Returns:
            Sanitized value.
        """
        if not isinstance(value, str):
            return str(value)

        sanitized = value

        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, sanitized):
                sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)

        return sanitized

    def render(self, data: dict[str, str]) -> str:
        """
        Render template with data and sanitize for prompt injection.

        Args:
            data: Dictionary of field values.

        Returns:
            Rendered prompt string with sanitized values.

        Raises:
            KeyError: If required field is missing from data.
        """
        sanitized_data = {
            key: self._sanitize_value(value) if isinstance(value, str) else value
            for key, value in data.items()
        }
        return self.template.format(**sanitized_data)

    def get_fields(self) -> list[str]:
        """
        Extract field names from template.

        Returns:
            List of field names used in template.
        """
        return [
            field_name
            for _, field_name, _, _ in self._formatter.parse(self.template)
            if field_name is not None
        ]
