"""Tests for configuration."""

from pathlib import Path

import pytest
import yaml

from agents.utils.config import JobConfig, load_config


def test_load_config_from_yaml(tmp_path: Path) -> None:
    """Test loading config from YAML file."""
    config_file = tmp_path / "config.yaml"
    config_data = {
        "llm": {
            "model": "gpt-4o-mini",
            "temperature": 0.5,
            "max_tokens": 1000,
        },
        "processing": {
            "mode": "sequential",
            "max_retries": 5,
        },
        "prompt": "Translate {text} to Spanish",
        "output": {
            "format": "json",
        },
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_file))

    assert config.llm.model == "gpt-4o-mini"
    assert config.llm.temperature == 0.5
    assert config.processing.mode == "sequential"
    assert config.prompt == "Translate {text} to Spanish"


def test_config_defaults() -> None:
    """Test config with default values."""
    config = JobConfig(
        llm={"model": "gpt-4o-mini", "api_key": "test"},
        prompt="Test {field}",
    )

    assert config.llm.temperature == 0.7  # default
    assert config.processing.mode == "async"  # default
    assert config.processing.batch_size == 10  # default
