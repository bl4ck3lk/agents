# Web App Deployment Design

**Date:** 2025-12-25
**Status:** Design Complete, Ready for Implementation

## Overview

Transform the agents CLI batch processing tool into a cloud SaaS web application where users can upload CSV/JSON files, provide prompts, and process data in the background.

## Requirements Summary

| Aspect | Choice |
|--------|--------|
| Deployment | Cloud SaaS (multi-tenant) |
| Auth | Social login (Google, GitHub) + email/password + magic links |
| Storage | Cloud object storage (S3/GCS/R2) |
| Jobs | **TaskQ** (existing Gleam project at ~/Projects/taskqworker) |
| Database | PostgreSQL (shared with TaskQ) |
| Frontend | Full web UI (Next.js 14) |
| API Keys | BYOK + managed option |

## Architecture

**Three-service architecture:**
1. **Web API** (Python/FastAPI) - User-facing, handles auth, enqueues tasks
2. **TaskQ** (Gleam/Erlang) - Queue management, worker coordination, retries
3. **Processing Service** (Python/FastAPI) - LLM processing, called by TaskQ workers

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                    Next.js Application                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Login   │  │  Upload  │  │   Jobs   │  │ Results  │        │
│  │  Page    │  │  Page    │  │  List    │  │  Viewer  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │ API Calls
┌────────────────────────────▼────────────────────────────────────┐
│                 WEB API (FastAPI - Python)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Auth       │  │  Jobs API   │  │  Files API  │             │
│  │  (OAuth2)   │  │  (Enqueue)  │  │  (Upload)   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                         │ INSERT INTO tasks                     │
└─────────────────────────┼───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                      PostgreSQL                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  Web App Tables  │  │  TaskQ Tables    │                     │
│  │  - users         │  │  - queues        │                     │
│  │  - api_keys      │  │  - tasks         │                     │
│  │  - web_jobs      │  │  - task_history  │                     │
│  │  - usage         │  │  - schedules     │                     │
│  └──────────────────┘  └──────────────────┘                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │ SKIP LOCKED
┌─────────────────────────▼───────────────────────────────────────┐
│                   TaskQ (Gleam/Erlang)                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Workers Pool (OTP GenServers)                          │   │
│  │  - Claims tasks from PostgreSQL                         │   │
│  │  - Handles retries, circuit breaking                    │   │
│  │  - Tracks progress in task_history                      │   │
│  │  - Admin UI at /admin                                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                          │ HTTP POST /process                   │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              PROCESSING SERVICE (FastAPI - Python)              │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  POST /process                                          │    │
│  │  - Receives: file_url, prompt, config, api_key         │    │
│  │  - Uses: ProcessingEngine, LLMClient                   │    │
│  │  - Streams results to S3                               │    │
│  │  - Returns: {success, results_url, stats}              │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
│  (Reuses existing agents/core/* code)                           │
└──────────────────────────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │     S3      │
                    │  (Files)    │
                    └─────────────┘
```

## Database Schema

Web app tables (new) + TaskQ tables (existing):

```sql
-- =====================
-- WEB APP TABLES (new)
-- =====================

-- Users (managed by fastapi-users)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  hashed_password TEXT,
  name TEXT,
  avatar_url TEXT,
  is_active BOOLEAN DEFAULT true,
  is_verified BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- User's stored LLM API keys (encrypted)
CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users ON DELETE CASCADE,
  provider TEXT NOT NULL,        -- 'openai', 'anthropic', etc.
  encrypted_key TEXT NOT NULL,   -- encrypted with server secret
  name TEXT,                     -- user-friendly label
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Web jobs (links user to TaskQ task)
CREATE TABLE web_jobs (
  id TEXT PRIMARY KEY,           -- job_20231119_143022
  user_id UUID REFERENCES users ON DELETE CASCADE,
  taskq_task_id UUID,            -- FK to TaskQ tasks table
  input_file_url TEXT NOT NULL,
  output_file_url TEXT,
  prompt TEXT NOT NULL,
  model TEXT NOT NULL,
  config JSONB,
  total_units INT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Usage tracking (for billing if managed keys)
CREATE TABLE usage (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users ON DELETE CASCADE,
  job_id TEXT REFERENCES web_jobs ON DELETE CASCADE,
  tokens_input INT DEFAULT 0,
  tokens_output INT DEFAULT 0,
  cost_usd DECIMAL(10, 6) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- =====================
-- TASKQ TABLES (existing in taskqworker)
-- =====================
-- queues, tasks, task_history, schedules, cluster_nodes
-- See ~/Projects/taskqworker for schema
```

## TaskQ Integration

### Task Payload Structure

When Web API creates a job, it inserts into TaskQ's `tasks` table:

```json
{
  "queue_id": "llm_processing",
  "payload": {
    "web_job_id": "job_20231119_143022",
    "file_url": "s3://bucket/uploads/file.csv",
    "prompt": "Translate '{text}' to Spanish",
    "model": "gpt-4o-mini",
    "config": { "batch_size": 10, "max_tokens": 1000 },
    "api_key_encrypted": "...",
    "results_url": "s3://bucket/results/job_123/results.jsonl",
    "callback_url": "http://processing-service:8001/process"
  },
  "priority": 5,
  "idempotency_key": "job_20231119_143022"
}
```

### TaskQ Worker Handler (Gleam)

```gleam
pub fn handle_llm_task(payload: LLMPayload) -> Result(String, String) {
  // Call Python processing service via HTTP
  let response = http.post(
    payload.callback_url,
    json.encode(payload),
    [Header("Content-Type", "application/json")]
  )

  case response {
    Ok(resp) if resp.status == 200 -> Ok(resp.body)
    Ok(resp) -> Error("Processing failed: " <> resp.body)
    Error(e) -> Error("HTTP error: " <> e)
  }
}
```

### Progress Tracking

- TaskQ's `task_history` table tracks each attempt
- Web API queries `task_history` + `tasks` for progress
- Processing service updates S3 incrementally (existing pattern)
- Frontend polls Web API for status

## API Endpoints

### Auth Endpoints
```
POST /auth/register         -> email/password registration
POST /auth/login            -> returns JWT token
POST /auth/login/google     -> OAuth redirect
POST /auth/login/github     -> OAuth redirect
POST /auth/magic-link       -> send magic link email
GET  /auth/verify           -> verify magic link token
GET  /auth/me               -> current user info
```

### File Endpoints
```
POST /files/upload          -> returns presigned S3 upload URL
POST /files/confirm         -> validate file, count rows
GET  /files/{file_id}       -> get presigned download URL
```

### Job Endpoints
```
POST /jobs                  -> create job (inserts to TaskQ tasks)
GET  /jobs                  -> list user's jobs (paginated)
GET  /jobs/{id}             -> job details + progress (from TaskQ)
GET  /jobs/{id}/results     -> paginated results from S3
POST /jobs/{id}/cancel      -> cancel (update TaskQ task status)
DELETE /jobs/{id}           -> delete job and files
```

### API Key Management
```
POST /api-keys              -> store encrypted key
GET  /api-keys              -> list stored keys (masked)
DELETE /api-keys/{id}       -> remove key
```

### Processing Service Endpoint
```
POST /process               -> called by TaskQ workers
  Request: { file_url, prompt, model, config, api_key, results_url }
  Response: { success, processed, failed, error? }
```

## File Upload & Processing Flow

### Upload Flow
1. User selects file in UI
2. Frontend calls `POST /files/upload` with filename, size, type
3. Backend generates presigned S3 upload URL (15 min expiry)
4. Frontend uploads directly to S3
5. Frontend calls `POST /files/confirm` with file_id
6. Backend validates format, counts rows, returns metadata

### Processing Flow
1. User configures job (prompt, model, settings) and submits
2. `POST /jobs`:
   - Creates `web_jobs` record
   - Inserts task into TaskQ's `tasks` table
   - Returns `job_id` immediately
3. TaskQ worker claims task (SKIP LOCKED)
4. Worker calls Processing Service `/process`
5. Processing Service:
   - Downloads file from S3
   - Creates adapter (CSV/JSON/etc)
   - Runs `ProcessingEngine` with streaming
   - Writes results incrementally to S3
   - Returns stats to worker
6. TaskQ records result in `task_history`
7. Frontend polls `GET /jobs/{id}` for progress

## Frontend Structure

```
web/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── verify/page.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── jobs/
│   │   │   ├── page.tsx
│   │   │   ├── new/page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── settings/
│   │       ├── page.tsx
│   │       └── api-keys/page.tsx
│   └── api/
├── components/
│   ├── FileUploader.tsx
│   ├── PromptEditor.tsx
│   ├── JobProgress.tsx
│   └── ResultsTable.tsx
└── lib/
    ├── api.ts
    └── auth.ts
```

Tech stack: Next.js 14, Tailwind CSS, shadcn/ui, React Query

## Implementation Phases

### Phase 1: Infrastructure & TaskQ Integration
- [ ] Set up PostgreSQL with web app tables
- [ ] Add S3-compatible storage layer (MinIO for dev)
- [ ] Create TaskQ queue for LLM processing
- [ ] Build Processing Service with `/process` endpoint
- [ ] Test end-to-end: insert task -> TaskQ -> Processing -> S3

**Files to modify/create:**
- `agents/db/` (new) - SQLAlchemy models, migrations
- `agents/storage/` (new) - S3 client abstraction
- `agents/processing_service/` (new) - FastAPI app for workers
- `taskqworker/` - Add llm_processing queue handler

### Phase 2: Authentication
- [ ] Integrate `fastapi-users` with OAuth providers
- [ ] Add API key encryption/storage
- [ ] Add JWT middleware + route protection
- [ ] Email service for magic links (Resend/SendGrid)

**Files to modify/create:**
- `agents/api/auth/` (new) - auth routes and config
- `agents/api/deps.py` (new) - dependency injection
- `agents/db/models/user.py` (new)

### Phase 3: Web API Jobs
- [ ] Add user scoping to job endpoints
- [ ] File upload with presigned URLs
- [ ] Job creation -> TaskQ integration
- [ ] Progress tracking from TaskQ tables
- [ ] Usage tracking for billing

**Files to modify/create:**
- `agents/api/routes/files.py` (new)
- `agents/api/routes/jobs.py` (new)
- `agents/api/app.py` - refactor

### Phase 4: Frontend
- [ ] Next.js project setup with auth
- [ ] Job creation wizard
- [ ] Job list + detail views
- [ ] Results viewer with export

**Files to create:**
- `web/` (new Next.js project)

### Phase 5: Production Readiness
- [ ] Rate limiting
- [ ] Error monitoring (Sentry)
- [ ] API documentation (OpenAPI)
- [ ] User guide
- [ ] Docker Compose for all services
- [ ] Kubernetes manifests (optional)

## Key Dependencies to Add

```toml
# Backend (pyproject.toml)
sqlalchemy = "^2.0"
alembic = "^1.13"
asyncpg = "^0.29"
boto3 = "^1.34"
fastapi-users = {extras = ["sqlalchemy", "oauth"], version = "^13.0"}
python-jose = "^3.3"
cryptography = "^41.0"
resend = "^0.5"  # for magic links
```

```json
// Frontend (package.json)
{
  "dependencies": {
    "next": "^14.0",
    "react": "^18.0",
    "tailwindcss": "^3.4",
    "@tanstack/react-query": "^5.0",
    "@radix-ui/react-*": "latest"
  }
}
```

## Existing Code to Preserve

The following core components remain unchanged:
- `agents/core/engine.py` - ProcessingEngine
- `agents/core/llm_client.py` - LLMClient
- `agents/core/prompt.py` - PromptTemplate
- `agents/core/postprocessor.py` - PostProcessor
- `agents/adapters/*` - All file format adapters
- `agents/utils/config.py` - JobConfig models
- `agents/utils/incremental_writer.py` - Results writer

## Security Considerations

- API keys encrypted at rest with Fernet (server secret)
- Presigned URLs expire after 15 minutes
- All endpoints require authentication
- Jobs scoped to authenticated user
- Rate limiting per user (100 req/min default)
- Input validation on file uploads (max 100MB, allowed types)
- TaskQ workers run in separate network segment
- Processing service not exposed to internet

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Load Balancer                         │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
│  Next.js      │ │  FastAPI  │ │  TaskQ Admin  │
│  Frontend     │ │  Web API  │ │  Dashboard    │
│  (Vercel?)    │ │  (Docker) │ │  (Phoenix)    │
└───────────────┘ └─────┬─────┘ └───────────────┘
                        │
                ┌───────▼───────┐
                │  PostgreSQL   │
                │  (RDS/Supabase)│
                └───────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌─────▼─────┐ ┌───────▼───────┐
│  TaskQ Node 1 │ │  TaskQ    │ │  Processing   │
│  (Gleam)      │ │  Node N   │ │  Service      │
│               │ │           │ │  (Python)     │
└───────────────┘ └───────────┘ └───────────────┘
                                        │
                                ┌───────▼───────┐
                                │      S3       │
                                │  (R2/Minio)   │
                                └───────────────┘
```

## Next Steps

1. Review and approve this plan
2. Set up development environment (Docker Compose)
3. Begin Phase 1: Infrastructure & TaskQ Integration
