"""Configuration management."""

import os

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    temperature: float = 0.7
    max_tokens: int = 500


class ProcessingConfig(BaseModel):
    """Processing configuration."""

    mode: str = "async"
    batch_size: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0


class OutputConfig(BaseModel):
    """Output configuration."""

    format: str = "json"
    merge_strategy: str = "extend"


class JobConfig(BaseModel):
    """Complete job configuration."""

    llm: LLMConfig
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    prompt: str


def load_config(path: str) -> JobConfig:
    """
    Load configuration from YAML file.

    Args:
        path: Path to config file.

    Returns:
        Loaded configuration.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    return JobConfig(**data)
