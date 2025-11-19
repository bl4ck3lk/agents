"""Prompt template for LLM requests."""

from string import Formatter


class PromptTemplate:
    """Template for rendering prompts with data."""

    def __init__(self, template: str) -> None:
        """
        Initialize prompt template.

        Args:
            template: Template string with {field} placeholders.
        """
        self.template = template
        self._formatter = Formatter()

    def render(self, data: dict[str, str]) -> str:
        """
        Render template with data.

        Args:
            data: Dictionary of field values.

        Returns:
            Rendered prompt string.

        Raises:
            KeyError: If required field is missing from data.
        """
        return self.template.format(**data)

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
