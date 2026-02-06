# Agents

LLM batch processing platform for processing large datasets with LLMs. Available as both a CLI tool and a full-featured web application.

**Features:**
- Process CSV, JSON, JSONL, text, and SQLite files
- Sequential or concurrent batch processing
- Any OpenAI-compatible API (OpenAI, Anthropic via OpenRouter, etc.)
- Resume interrupted jobs
- Web UI with job management, progress tracking, and results viewer
- Secure API key storage with encryption
- Multi-user support with authentication

## Table of Contents

- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Web Application](#web-application)
- [Development Setup](#development-setup)
- [Testing](#testing)
- [Deployment](#deployment)
- [Configuration Reference](#configuration-reference)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)

## Make Commands Quick Reference

| Command | Description |
|---------|-------------|
| `make dev-full` | **Start everything** (recommended for development) |
| `make dev` | Start API + Frontend only (no background processing) |
| `make stop` | Stop all services |
| `make check-tasks` | View TaskQ task statuses |
| `make check-jobs` | View WebJob statuses |
| `make db-shell` | Open interactive database shell |
| `make test` | Run all tests |
| `make check` | Run linting + type checking + tests |
| `make clean` | Stop services and clean generated files |

---

## Quick Start

### CLI Only (Simple)

```bash
# Install
uv pip install -e .

# Set API key
export OPENAI_API_KEY=sk-...

# Process a file
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"
```

### Full Web Application

```bash
# Clone and setup
git clone <repo-url>
cd agents

# Install dependencies
make install

# Start everything with one command
make dev-full

# Open http://localhost:3000
```

> **Note:** Requires TaskQ worker at `~/Projects/taskqworker`. See [Development Setup](#development-setup) for details.

---

## CLI Usage

### Basic Commands

```bash
# Process a file
agents process INPUT_FILE OUTPUT_FILE [OPTIONS]

# Resume an interrupted job
agents resume JOB_ID [OPTIONS]
```

### Command Options

```bash
agents process INPUT_FILE OUTPUT_FILE [OPTIONS]

Options:
  --config PATH              Path to config YAML file
  --prompt TEXT              Prompt template with {field} placeholders
  --model TEXT               LLM model to use (default: gpt-4o-mini)
  --api-key TEXT             OpenAI API key (or set OPENAI_API_KEY)
  --base-url TEXT            API base URL for OpenAI-compatible APIs
  --mode [sequential|async]  Processing mode (default: sequential)
  --batch-size INTEGER       Concurrent requests in async mode (default: 10)
  --max-tokens INTEGER       Maximum tokens in LLM response (default: 1500)
  --preview INTEGER          Preview K random samples before processing all
  --checkin-interval INTEGER Pause every N entries to ask user to continue
  --circuit-breaker INTEGER  Trip after N consecutive fatal errors (default: 5, 0 to disable)
  --no-post-process          Disable JSON extraction from LLM output
  --no-merge                 Keep parsed JSON in 'parsed' field
  --include-raw              Include raw LLM output in result
```

### Using Config Files

```yaml
# job.yaml
llm:
  model: gpt-4o-mini
  temperature: 0.7
  max_tokens: 1500

processing:
  mode: async
  batch_size: 20
  checkin_interval: 100

prompt: |
  Translate '{text}' to Spanish.
  Return as JSON with keys: translation, confidence
```

```bash
agents process input.csv output.csv --config job.yaml
```

### Resuming Jobs

Jobs save progress to `.checkpoints/` and can be resumed after interruption:

```bash
# Find job IDs
ls .checkpoints/.progress_*.json

# Resume
agents resume job_20251126_205528
```

---

## Web Application

The web application provides a full-featured UI for batch processing with:
- User authentication (email/password, OAuth)
- Secure API key storage
- File upload and job management
- Real-time progress tracking
- Results viewer with pagination and export

### Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Next.js       │────▶│   FastAPI       │────▶│   PostgreSQL    │
│   Frontend      │     │   Web API       │     │   Database      │
│   :3000         │     │   :8002         │     │   :5433         │
└─────────────────┘     └────────┬────────┘     └────────┬────────┘
                                 │                       │
                        ┌────────▼────────┐     ┌────────▼────────┐
                        │   MinIO/S3      │     │  TaskQ Worker   │
                        │   Storage       │     │  (Gleam)        │
                        │   :9000         │     │  Polls DB       │
                        └─────────────────┘     └────────┬────────┘
                                                         │
                                                ┌────────▼────────┐
                                                │ Processing Svc  │
                                                │ (Python)        │
                                                │ :8001           │
                                                └─────────────────┘
```

### Processing Flow

1. **User uploads file** → Presigned URL → Direct upload to MinIO/S3
2. **User creates job** → Web API inserts task into TaskQ's `tasks` table
3. **TaskQ Worker polls** → Claims pending tasks from PostgreSQL (SKIP LOCKED)
4. **Worker calls Processing Service** → Downloads file, processes with LLM, uploads results
5. **Processing Service updates job** → User sees real-time progress
6. **Job completes** → User downloads enriched results

---

## Development Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker and Docker Compose
- uv (recommended) or pip
- Gleam (for TaskQ worker) - install from https://gleam.run

### TaskQ Worker Setup

The TaskQ worker is a separate Gleam project that handles background job processing.
It must be located at `~/Projects/taskqworker`:

```bash
# Clone TaskQ worker (if not already present)
cd ~/Projects
git clone <taskqworker-repo-url> taskqworker

# Build it
cd taskqworker
gleam build
```

The `make dev-full` command will automatically start the TaskQ worker from this location.

### Quick Start (One Command)

```bash
# Install dependencies
make install

# Start EVERYTHING with a single command
make dev-full
```

This starts:
- **PostgreSQL** (port 5433) - Database
- **MinIO** (port 9000, console 9001) - S3-compatible storage
- **Redis** (port 6380) - Cache
- **Web API** (port 8002) - FastAPI backend
- **Frontend** (port 3000) - Next.js UI
- **Processing Service** (port 8001) - LLM job processor
- **TaskQ Worker** - Background job queue (Gleam)

Open http://localhost:3000 to access the application.

### Alternative: Partial Startup

```bash
# Start just API + Frontend (no background processing)
make dev

# Or start services separately:
make services           # PostgreSQL, MinIO, Redis only
make api-dev            # FastAPI backend only
make frontend-dev       # Next.js frontend only
make processing-service # Processing service only
make taskq-worker       # TaskQ worker only
```

### Option 2: Manual Setup

#### 1. Install Python Dependencies

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

#### 2. Start Infrastructure Services

```bash
docker-compose up -d postgres minio redis
```

#### 3. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your settings (see Configuration Reference)
```

#### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head
```

#### 5. Start Backend API

```bash
# Development mode with auto-reload
uvicorn agents.api.app:app --reload --port 8002

# Or using the console script
PORT=8002 RELOAD=true agents-api
```

#### 6. Start Frontend

```bash
cd web
npm install
npm run dev
```

#### 7. Access the Application

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8002/docs
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

### Monitoring & Debugging

```bash
# Check job queue status
make check-tasks    # View TaskQ task statuses

# Check web jobs status
make check-jobs     # View WebJob statuses

# Open database shell
make db-shell       # Interactive psql session

# View logs
make logs           # All Docker service logs
make logs-api       # API logs only
make logs-db        # Database logs only
```

### Development Workflow

```bash
# Format code
make format

# Run linters
make lint

# Run type checking
make typecheck

# Run all checks
make check

# Run tests
make test

# Stop all services
make stop

# Clean up
make clean
```

---

## Testing

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Specific test file
pytest tests/test_engine.py -v

# Specific test
pytest tests/test_engine.py::test_process_sequential -v
```

### Test Categories

```bash
# Unit tests only
pytest tests/ -m "not integration"

# Integration tests (requires services)
pytest tests/ -m integration
```

### Frontend

```bash
cd web

# Run linting
npm run lint

# Build for production
npm run build
```

> **Note:** Frontend testing infrastructure (Jest/Vitest) is not yet configured.

---

## Deployment

### Environment Variables

See `.env.example` for all available options. Required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT signing key (32+ chars) | `your-secret-key-here` |
| `ENCRYPTION_KEY` | API key encryption key (Fernet) | `your-32-byte-encryption-key!!` |
| `INTERNAL_SERVICE_TOKEN` | Processing service auth token | `your-service-token` |
| `S3_ENDPOINT_URL` | S3/MinIO endpoint | `https://s3.amazonaws.com` |
| `AWS_ACCESS_KEY_ID` | S3 access key | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | S3 secret key | `...` |
| `S3_BUCKET_NAME` | S3 bucket name | `agents-production` |
| `REDIS_URL` | Redis URL for rate limiting | `redis://localhost:6379` |

### Option 1: Docker Compose (Simple)

```bash
# Build and start all services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f
```

### Option 2: Platform-Specific

#### Vercel (Frontend) + Railway/Render (Backend)

**Frontend (Vercel):**
```bash
cd web
vercel deploy --prod
```

Set environment variables in Vercel dashboard:
- `NEXT_PUBLIC_API_URL`: Your backend API URL

**Backend (Railway):**
1. Connect GitHub repo
2. Set root directory to `/`
3. Set start command: `agents-api`
4. Add environment variables from `.env.example`

#### AWS (ECS/Fargate)

See `docs/deployment/cloud.md` for detailed instructions.

### Production Checklist

- [ ] Set strong `SECRET_KEY` and `ENCRYPTION_KEY`
- [ ] Set `INTERNAL_SERVICE_TOKEN` for processing service auth
- [ ] Configure PostgreSQL with SSL
- [ ] Set up S3 bucket with appropriate permissions
- [ ] Set `REDIS_URL` for distributed rate limiting
- [ ] Configure Sentry for error monitoring (`SENTRY_DSN`)
- [ ] Set `ENVIRONMENT=production` (enables env var validation at startup)
- [ ] Configure CORS origins (`CORS_ORIGINS`)
- [ ] Set up SSL/TLS termination
- [ ] Configure allowed models (`ALLOWED_MODELS`)
- [ ] Enable usage limits (`ENFORCE_USAGE_LIMITS=true`)
- [ ] Enable content moderation (`ENABLE_CONTENT_MODERATION=true`)
- [ ] Set up database backups
- [ ] Configure logging and monitoring

---

## Configuration Reference

### Environment Variables

```bash
# === Required ===
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agents
SECRET_KEY=your-secret-key-change-in-production
ENCRYPTION_KEY=your-32-byte-encryption-key-here

# S3 Storage
S3_ENDPOINT_URL=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=agents
AWS_REGION=us-east-1

# === Security ===

# Internal service auth (processing service <-> TaskQ worker)
INTERNAL_SERVICE_TOKEN=your-internal-service-token

# Redis for distributed rate limiting (recommended for multi-instance)
REDIS_URL=redis://localhost:6380

# Stuck job recovery timeout (minutes, default: 30)
STUCK_JOB_TIMEOUT_MINUTES=30

# === Optional ===

# OAuth Providers
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# Email (for magic links, password reset)
RESEND_API_KEY=

# Error Monitoring
SENTRY_DSN=
ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1

# CORS
CORS_ORIGINS=http://localhost:3000

# Model validation
ALLOWED_MODELS=gpt-4o,gpt-4o-mini,gpt-4-turbo,anthropic/claude-3.5-sonnet

# Usage and moderation
ENFORCE_USAGE_LIMITS=true
ENABLE_CONTENT_MODERATION=true

# Presigned URL expiry (seconds)
S3_PRESIGNED_EXPIRY=900

# Debug
SQL_ECHO=false
RELOAD=false
```

### Rate Limits

Default rate limits per authenticated user (backed by Redis when `REDIS_URL` is set, otherwise in-memory):

| Endpoint | Limit |
|----------|-------|
| Job creation | 20/minute |
| File uploads | 30/minute |
| Prompt testing | 30/minute |
| Model comparison | 10/minute |

> **Note:** In-memory rate limiting is not suitable for multi-instance deployments. Set `REDIS_URL` in production.

---

## API Documentation

### Interactive Docs

- **Swagger UI**: http://localhost:8002/docs
- **ReDoc**: http://localhost:8002/redoc

### Key Endpoints

#### Authentication

```bash
# Register
curl -X POST http://localhost:8002/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Login
curl -X POST http://localhost:8002/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123"
# Returns: {"access_token": "...", "token_type": "bearer"}
```

#### Jobs

```bash
# Create job
curl -X POST http://localhost:8002/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_key": "uploads/user-id/file.csv",
    "prompt": "Translate {text} to Spanish",
    "model": "gpt-4o-mini"
  }'

# List jobs
curl http://localhost:8002/jobs \
  -H "Authorization: Bearer $TOKEN"

# Get job details
curl http://localhost:8002/jobs/job_20251225_120000 \
  -H "Authorization: Bearer $TOKEN"

# Get results
curl http://localhost:8002/jobs/job_20251225_120000/results \
  -H "Authorization: Bearer $TOKEN"
```

#### Files

```bash
# Get upload URL
curl -X POST http://localhost:8002/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename": "data.csv", "content_type": "text/csv"}'
# Returns presigned URL for direct upload to S3

# Confirm upload
curl -X POST http://localhost:8002/files/confirm \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_id": "...", "key": "uploads/..."}'
```

---

## Troubleshooting

### Common Issues

**Database connection errors:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection (note: port 5433, not 5432)
psql postgresql://postgres:postgres@localhost:5433/agents -c "SELECT 1"
```

**MinIO/S3 errors:**
```bash
# Check MinIO is running
docker-compose ps minio

# Check bucket exists (using MinIO console)
open http://localhost:9001  # Login: minioadmin/minioadmin
```

**Jobs stuck in pending:**
```bash
# Check if TaskQ worker is running
# Look for "Workers are now polling for tasks!" in terminal

# Check task status
make check-tasks

# Check for task errors
make db-shell
# Then: SELECT * FROM tasks WHERE status = 'dead_letter';
```

**Tasks failing (dead_letter):**
```bash
# View task errors
make db-shell
# Then: SELECT id, last_error FROM tasks WHERE status = 'dead_letter';

# Reset failed tasks to retry
# UPDATE tasks SET status = 'pending', attempts = 0, last_error = NULL WHERE status = 'dead_letter';
```

**Processing Service not running or returning 401:**
```bash
# Check if port 8001 is responding
curl http://localhost:8001/health

# Start it manually if needed
make processing-service

# If getting 401 Unauthorized on /process, ensure INTERNAL_SERVICE_TOKEN
# matches between the API and processing service environments
```

**Frontend can't connect to API:**
- Check `NEXT_PUBLIC_API_URL` is set correctly
- Check CORS origins include frontend URL
- Check API is running on port 8002

**Migration errors:**
```bash
# Check current revision
uv run alembic current

# Show migration history
uv run alembic history

# Downgrade if needed
uv run alembic downgrade -1
```

### Logs & Monitoring

```bash
# View job queue status
make check-tasks
make check-jobs

# Open database shell
make db-shell

# All Docker service logs
docker-compose logs -f

# Watch specific queries
make db-shell
# Then: SELECT id, status, processed_units FROM web_jobs ORDER BY created_at DESC LIMIT 5;
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Run checks: `make check`
5. Commit with conventional commits: `git commit -m "feat: add new feature"`
6. Push and create a pull request

---

## License

MIT License - see LICENSE file for details.
