"""Configuration management."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load .env file when this module is imported
# Look for .env in the project root (parent of agents package)
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    temperature: float = 0.7
    max_tokens: int = 1500


class ProcessingConfig(BaseModel):
    """Processing configuration."""

    mode: str = "async"
    batch_size: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0
    checkin_interval: int | None = None  # Pause every N entries to ask user to continue
    circuit_breaker_threshold: int = 5


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
