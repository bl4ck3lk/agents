# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package installation
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY README.md .
COPY agents/ agents/
COPY alembic/ alembic/
COPY alembic.ini .

# Install dependencies
RUN uv pip install --system -e .

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --from=builder /app/agents /app/agents
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Default command
CMD ["agents-api"]
