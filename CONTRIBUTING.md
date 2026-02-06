# Contributing to Agents

Thank you for your interest in contributing to Agents! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker and Docker Compose
- uv (recommended) or pip
- Git

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd agents

# Copy environment config
cp .env.example .env

# Install all dependencies
make install

# Start development environment
make dev
```

This starts:
- PostgreSQL on port 5433
- MinIO (S3) on port 9000 (console: 9001)
- Redis on port 6380
- FastAPI backend on port 8002
- Processing Service on port 8001
- Next.js frontend on port 3000

## Project Structure

```
agents/
├── agents/                 # Python backend
│   ├── adapters/          # File format adapters (CSV, JSON, etc.)
│   ├── api/               # FastAPI application
│   │   ├── auth/          # Authentication (fastapi-users)
│   │   └── routes/        # API endpoints
│   ├── core/              # Core processing engine
│   ├── db/                # Database models and migrations
│   ├── processing_service/ # Worker service for TaskQ
│   ├── storage/           # S3 storage client
│   └── utils/             # Utilities and config
├── web/                   # Next.js frontend
│   ├── app/               # App router pages
│   ├── components/        # React components
│   └── lib/               # API client and utilities
├── tests/                 # Python tests
├── alembic/               # Database migrations
└── docs/                  # Documentation
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/my-bugfix
```

### 2. Make Changes

- Write code following the project style
- Add tests for new functionality
- Update documentation as needed

### 3. Run Checks

```bash
# Format code
make format

# Run linter
make lint

# Run type checker
make typecheck

# Run tests
make test

# Or run all at once
make check
```

### 4. Commit Changes

We use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Features
git commit -m "feat: add new file format adapter"

# Bug fixes
git commit -m "fix: correct pagination in job list"

# Documentation
git commit -m "docs: update API documentation"

# Refactoring
git commit -m "refactor: simplify authentication flow"

# Tests
git commit -m "test: add integration tests for jobs API"
```

### 5. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

## Code Style

### Python

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

```python
# Good
async def create_job(
    body: JobCreateRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
) -> JobResponse:
    """Create a new processing job."""
    ...

# Avoid
def create_job(body, user, session):
    ...
```

### TypeScript/React

- Use TypeScript for all new code
- Use functional components with hooks
- Follow React naming conventions

```typescript
// Good
interface JobListProps {
  jobs: Job[];
  onSelect: (job: Job) => void;
}

export function JobList({ jobs, onSelect }: JobListProps) {
  ...
}
```

## Testing

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test
pytest tests/test_engine.py::test_name -v

# Frontend tests
make test-frontend
```

### Writing Tests

```python
# tests/test_example.py
import pytest
from agents.core.engine import ProcessingEngine

@pytest.mark.asyncio
async def test_process_batch():
    engine = ProcessingEngine(...)
    results = await engine.process_batch(items)
    assert len(results) == len(items)
```

## Database Migrations

When changing database models:

```bash
# Create a new migration
make db-revision
# Enter a descriptive message when prompted

# Apply migrations
make db-upgrade

# Rollback if needed
make db-downgrade
```

## Local Database Access

The development environment uses PostgreSQL running in Docker. Here's how to access it:

### Connection Details

When running `make dev`, PostgreSQL is available at:

| Setting    | Value                                              |
|------------|---------------------------------------------------|
| Host       | `localhost`                                        |
| Port       | `5433` (mapped from container's 5432)             |
| Database   | `agents`                                           |
| Username   | `postgres`                                         |
| Password   | `postgres`                                         |
| URL        | `postgresql://postgres:postgres@localhost:5433/agents` |

### Connecting with psql

```bash
# Using psql directly (requires postgresql client installed)
psql -h localhost -p 5433 -U postgres -d agents

# Or use docker exec to connect within the container
docker exec -it agents-postgres psql -U postgres -d agents
```

### Connecting with a GUI

Use any PostgreSQL GUI client (TablePlus, DBeaver, pgAdmin, etc.) with these settings:

- **Host:** localhost
- **Port:** 5433
- **User:** postgres
- **Password:** postgres
- **Database:** agents

### Useful SQL Commands

```sql
-- List all tables
\dt

-- Describe a table
\d users
\d jobs

-- View recent jobs
SELECT id, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 10;

-- View users
SELECT id, email, is_superuser, can_use_platform_key FROM users;

-- Grant platform key access to a user
UPDATE users SET can_use_platform_key = true WHERE email = 'your@email.com';

-- View usage records
SELECT * FROM usage ORDER BY created_at DESC LIMIT 10;

-- View platform API keys (admin only)
SELECT id, provider, name, is_active FROM platform_api_keys;

-- View model pricing
SELECT model_pattern, provider, input_cost_per_million, output_cost_per_million, markup_percentage
FROM model_pricing WHERE effective_to IS NULL;
```

### Running Migrations Manually

If you need to run migrations manually or debug issues:

```bash
# Check current migration status
make db-status

# Run migrations
make db-upgrade

# Generate a migration after model changes
make db-revision

# Roll back one migration
make db-downgrade
```

### Resetting the Database

To completely reset the database (useful for testing migrations):

```bash
# Stop containers and remove volumes
make dev-clean

# Start fresh
make dev
```

## API Development

### Adding a New Endpoint

1. Add route in `agents/api/routes/`
2. Add Pydantic schemas for request/response
3. Register router in `agents/api/app.py`
4. Add tests in `tests/`
5. Update API documentation if needed

### Example

All API endpoints require authentication. Use `Depends(current_active_user)`:

```python
# agents/api/routes/my_route.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agents.api.auth import current_active_user
from agents.db.models import User

router = APIRouter(prefix="/my-endpoint", tags=["MyTag"])

class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str

@router.post("", response_model=MyResponse)
async def my_endpoint(
    body: MyRequest,
    user: User = Depends(current_active_user),
) -> MyResponse:
    """Description for OpenAPI docs. Requires authentication."""
    return MyResponse(result=body.field.upper())
```

### Security Guidelines

When adding new endpoints or features:

- Always add `Depends(current_active_user)` to endpoints that access user data
- Never log API keys, tokens, or other secrets (use `logging`, not `print()`)
- Scope file/data access to the authenticated user (`user.id`)
- Validate and sanitize all user inputs
- Use parameterized queries; never interpolate user data into SQL
- Encrypt sensitive data at rest (see `agents/api/security.py`)
- Return generic error messages to clients (not stack traces or internal paths)

## Frontend Development

### Adding a New Page

1. Create page in `web/app/`
2. Add API types in `web/lib/api.ts`
3. Create components in `web/components/`

### Using the API Client

```typescript
import { jobsApi } from '@/lib/api';
import { useAuth } from '@/lib/auth';

function MyComponent() {
  const { token } = useAuth();

  useEffect(() => {
    if (token) {
      jobsApi.list(token).then(setJobs);
    }
  }, [token]);
}
```

## Documentation

- Update README.md for user-facing changes
- Add inline comments for complex logic
- Update API docs via docstrings (auto-generated)

## Getting Help

- Check existing issues and PRs
- Ask questions in discussions
- Tag maintainers for review

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
