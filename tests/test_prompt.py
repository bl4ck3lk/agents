"""Tests for prompt templating."""

import pytest

from agents.core.prompt import PromptTemplate


def test_prompt_template_simple() -> None:
    """Test simple prompt template rendering."""
    template = PromptTemplate("Translate '{word}' to Spanish")
    result = template.render({"word": "hello"})
    assert result == "Translate 'hello' to Spanish"


def test_prompt_template_multiple_fields() -> None:
    """Test template with multiple fields."""
    template = PromptTemplate("Translate '{word}' from {lang_from} to {lang_to}")
    result = template.render({"word": "hello", "lang_from": "English", "lang_to": "Spanish"})
    assert result == "Translate 'hello' from English to Spanish"


def test_prompt_template_missing_field() -> None:
    """Test template with missing field raises error."""
    template = PromptTemplate("Translate '{word}' to Spanish")
    with pytest.raises(KeyError):
        template.render({"text": "hello"})


def test_prompt_template_get_fields() -> None:
    """Test extracting field names from template."""
    template = PromptTemplate("Translate '{word}' from {lang_from} to {lang_to}")
    fields = template.get_fields()
    assert fields == ["word", "lang_from", "lang_to"]
