"""Database helpers for updating WebJob status during processing."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from agents.db.session import async_session_maker


async def update_job_status(
    job_id: str,
    status: str,
    processed: int | None = None,
    failed: int | None = None,
    total: int | None = None,
    output_url: str | None = None,
    error: str | None = None,
) -> None:
    """Update WebJob status in database.

    Args:
        job_id: The job ID to update
        status: New status (pending, processing, completed, failed)
        processed: Number of successfully processed units
        failed: Number of failed units
        total: Total units to process
        output_url: URL to output file (for completed jobs)
        error: Error message (for failed jobs)
    """
    async with async_session_maker() as session:
        # Build dynamic update with parameterized CASE expression
        updates: dict[str, Any] = {
            "job_id": job_id,
            "status": status,
            "processed": processed,
            "failed": failed,
            "total": total,
            "output_url": output_url,
            "error": error,
        }

        # Determine timestamp updates based on status
        now = datetime.now(UTC)
        started_at_value = None
        completed_at_value = None

        if status == "processing":
            started_at_value = now
        if status in ("completed", "failed"):
            completed_at_value = now

        await session.execute(
            text("""
                UPDATE web_jobs
                SET status = :status,
                    processed_units = COALESCE(:processed, processed_units),
                    failed_units = COALESCE(:failed, failed_units),
                    total_units = COALESCE(:total, total_units),
                    output_file_url = COALESCE(:output_url, output_file_url),
                    error_message = COALESCE(:error, error_message),
                    started_at = CASE
                        WHEN :status = 'processing' THEN :started_at
                        ELSE started_at
                    END,
                    completed_at = CASE
                        WHEN :status IN ('completed', 'failed') THEN :completed_at
                        ELSE completed_at
                    END
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
                "status": status,
                "processed": processed,
                "failed": failed,
                "total": total,
                "output_url": output_url,
                "error": error,
                "started_at": started_at_value,
                "completed_at": completed_at_value,
            },
        )
        await session.commit()


async def update_job_progress(
    job_id: str,
    processed: int,
    failed: int,
    total: int,
) -> None:
    """Update job progress without changing status.

    Args:
        job_id: The job ID to update
        processed: Number of successfully processed units
        failed: Number of failed units
        total: Total units to process
    """
    async with async_session_maker() as session:
        await session.execute(
            text("""
                UPDATE web_jobs
                SET processed_units = :processed,
                    failed_units = :failed,
                    total_units = :total
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
                "processed": processed,
                "failed": failed,
                "total": total,
            },
        )
        await session.commit()
