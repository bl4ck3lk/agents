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

# Default configuration constants
DEFAULT_MAX_TOKENS = 5000
DEFAULT_MODEL = "openai/gpt-5-mini"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_RETRIES = 3
DEFAULT_BATCH_SIZE = 10
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = "openai"
    model: str = DEFAULT_MODEL
    base_url: str | None = None
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS


class ProcessingConfig(BaseModel):
    """Processing configuration."""

    mode: str = "async"
    batch_size: int = DEFAULT_BATCH_SIZE
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = 1.0
    checkin_interval: int | None = None  # Pause every N entries to ask user to continue
    circuit_breaker_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD


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
