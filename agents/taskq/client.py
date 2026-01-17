"""Client for inserting tasks into TaskQ's PostgreSQL tables.

TaskQ is a separate Gleam service that manages a PostgreSQL-based job queue.
This client allows the Python web API to insert tasks directly into TaskQ's
tasks table, which TaskQ workers will then process.
"""

import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

QUEUE_NAME = "llm_processing"


async def get_queue_id(session: AsyncSession) -> str:
    """Get the llm_processing queue ID from TaskQ.

    Args:
        session: SQLAlchemy async session

    Returns:
        The UUID of the llm_processing queue

    Raises:
        ValueError: If the queue doesn't exist
    """
    result = await session.execute(
        text("SELECT id FROM queues WHERE name = :name"),
        {"name": QUEUE_NAME},
    )
    row = result.fetchone()
    if not row:
        raise ValueError(f"Queue '{QUEUE_NAME}' not found in TaskQ")
    return str(row[0])


async def enqueue_task(
    session: AsyncSession,
    payload: dict,
    idempotency_key: str | None = None,
    priority: int = 5,
) -> str:
    """Insert a task into TaskQ's tasks table.

    Args:
        session: SQLAlchemy async session
        payload: The task payload (will be JSON encoded)
        idempotency_key: Optional key to prevent duplicate tasks
        priority: Task priority (1-10, higher is more important)

    Returns:
        The UUID of the created task
    """
    queue_id = await get_queue_id(session)
    task_id = str(uuid4())

    await session.execute(
        text("""
            INSERT INTO tasks (
                id, queue_id, status, payload, priority,
                scheduled_at, attempts, max_attempts, idempotency_key
            )
            VALUES (
                :id, :queue_id, 'pending', CAST(:payload AS jsonb), :priority,
                NOW(), 0, 3, :idempotency_key
            )
        """),
        {
            "id": task_id,
            "queue_id": queue_id,
            "payload": json.dumps(payload),
            "priority": priority,
            "idempotency_key": idempotency_key,
        },
    )

    return task_id
