"""Storage configuration."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Configuration for S3-compatible storage."""

    endpoint_url: str | None
    access_key_id: str
    secret_access_key: str
    bucket_name: str
    region: str
    presigned_url_expiry: int  # seconds

    @classmethod
    def from_env(cls) -> StorageConfig:
        """Create config from environment variables."""
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not access_key or not secret_key:
            logger.warning(
                "AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY not set - using default "
                "development credentials. Set these env vars for production."
            )

        return cls(
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),  # None for AWS S3
            access_key_id=access_key or "minioadmin",
            secret_access_key=secret_key or "minioadmin",
            bucket_name=os.getenv("S3_BUCKET_NAME", "agents"),
            region=os.getenv("AWS_REGION", "us-east-1"),
            presigned_url_expiry=int(os.getenv("S3_PRESIGNED_EXPIRY", "900")),  # 15 min
        )
