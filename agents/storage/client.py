"""S3-compatible storage client."""

import io
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, BinaryIO
from uuid import uuid4

import aioboto3
import boto3
from botocore.config import Config

from agents.storage.config import StorageConfig


class StorageClient:
    """Client for S3-compatible object storage."""

    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self._session = aioboto3.Session()

        # Boto3 config for retries
        self._boto_config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            signature_version="s3v4",
        )

    @asynccontextmanager
    async def _get_client(self) -> Any:
        """Get async S3 client."""
        async with self._session.client(
            "s3",
            endpoint_url=self.config.endpoint_url,
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_access_key,
            region_name=self.config.region,
            config=self._boto_config,
        ) as client:
            yield client

    def _get_sync_client(self) -> Any:
        """Get sync S3 client."""
        return boto3.client(
            "s3",
            endpoint_url=self.config.endpoint_url,
            aws_access_key_id=self.config.access_key_id,
            aws_secret_access_key=self.config.secret_access_key,
            region_name=self.config.region,
            config=self._boto_config,
        )

    async def ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist."""
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self.config.bucket_name)
            except Exception:
                await client.create_bucket(
                    Bucket=self.config.bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.config.region}
                    if self.config.region != "us-east-1"
                    else {},
                )

    def generate_upload_key(self, user_id: str, filename: str) -> str:
        """Generate unique key for uploaded file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid4())[:8]
        ext = os.path.splitext(filename)[1]
        return f"uploads/{user_id}/{timestamp}_{unique_id}{ext}"

    def generate_results_key(self, job_id: str) -> str:
        """Generate key for job results."""
        return f"results/{job_id}/results.jsonl"

    def generate_output_key(self, job_id: str, filename: str) -> str:
        """Generate key for final output file."""
        ext = os.path.splitext(filename)[1] or ".csv"
        return f"outputs/{job_id}/output{ext}"

    async def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        max_size_mb: int = 100,
    ) -> dict[str, Any]:
        """Generate presigned URL for file upload."""
        async with self._get_client() as client:
            # Generate presigned POST data
            # Use starts-with condition for Content-Type to be more flexible
            conditions = [
                ["content-length-range", 0, max_size_mb * 1024 * 1024],
                ["starts-with", "$Content-Type", ""],  # Allow any content type
            ]

            presigned = await client.generate_presigned_post(
                Bucket=self.config.bucket_name,
                Key=key,
                Conditions=conditions,
                ExpiresIn=self.config.presigned_url_expiry,
            )

            # Add Content-Type to fields so frontend knows to include it
            fields = presigned["fields"]
            fields["Content-Type"] = content_type

            return {
                "url": presigned["url"],
                "fields": fields,
                "key": key,
                "expires_in": self.config.presigned_url_expiry,
            }

    async def generate_presigned_download_url(self, key: str) -> str:
        """Generate presigned URL for file download."""
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.config.bucket_name, "Key": key},
                ExpiresIn=self.config.presigned_url_expiry,
            )
            return url

    async def upload_file(
        self, key: str, data: BinaryIO | bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file to storage."""
        async with self._get_client() as client:
            if isinstance(data, bytes):
                data = io.BytesIO(data)

            await client.upload_fileobj(
                data,
                self.config.bucket_name,
                key,
                ExtraArgs={"ContentType": content_type},
            )

            return f"s3://{self.config.bucket_name}/{key}"

    async def download_file(self, key: str) -> bytes:
        """Download file from storage."""
        async with self._get_client() as client:
            response = await client.get_object(Bucket=self.config.bucket_name, Key=key)
            async with response["Body"] as stream:
                return await stream.read()

    async def download_file_to_path(self, key: str, local_path: str) -> None:
        """Download file to local path."""
        async with self._get_client() as client:
            await client.download_file(self.config.bucket_name, key, local_path)

    def download_file_sync(self, key: str, local_path: str) -> None:
        """Synchronously download file to local path."""
        client = self._get_sync_client()
        client.download_file(self.config.bucket_name, key, local_path)

    async def delete_file(self, key: str) -> None:
        """Delete file from storage."""
        async with self._get_client() as client:
            await client.delete_object(Bucket=self.config.bucket_name, Key=key)

    async def file_exists(self, key: str) -> bool:
        """Check if file exists."""
        async with self._get_client() as client:
            try:
                await client.head_object(Bucket=self.config.bucket_name, Key=key)
                return True
            except Exception:
                return False

    async def get_file_info(self, key: str) -> dict[str, Any] | None:
        """Get file metadata."""
        async with self._get_client() as client:
            try:
                response = await client.head_object(Bucket=self.config.bucket_name, Key=key)
                return {
                    "size": response["ContentLength"],
                    "content_type": response.get("ContentType"),
                    "last_modified": response.get("LastModified"),
                    "etag": response.get("ETag"),
                }
            except Exception:
                return None

    async def list_files(self, prefix: str) -> list[dict[str, Any]]:
        """List files with given prefix."""
        async with self._get_client() as client:
            response = await client.list_objects_v2(Bucket=self.config.bucket_name, Prefix=prefix)
            files = []
            for obj in response.get("Contents", []):
                files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"],
                    }
                )
            return files

    def get_s3_url(self, key: str) -> str:
        """Get S3 URL for a key."""
        return f"s3://{self.config.bucket_name}/{key}"

    def parse_s3_url(self, url: str) -> tuple[str, str]:
        """Parse S3 URL into bucket and key."""
        if url.startswith("s3://"):
            url = url[5:]
            parts = url.split("/", 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        raise ValueError(f"Invalid S3 URL: {url}")


# Global storage client instance
_storage_client: StorageClient | None = None


def get_storage_client() -> StorageClient:
    """Get or create storage client singleton."""
    global _storage_client
    if _storage_client is None:
        config = StorageConfig.from_env()
        _storage_client = StorageClient(config)
    return _storage_client
