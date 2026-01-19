# Security Review Checklist

Quick security checklist for code reviews and pull requests.

---

## Pre-Review Setup

Before reviewing, understand the change:
- [ ] What feature/fix is this?
- [ ] What data does it handle?
- [ ] Does it touch authentication, authorization, or user data?

---

## Quick Scan (All PRs)

Run on every PR before merging:

```bash
# From project root
./scripts/quick-scan.sh

# Or manually check for common issues
grep -rE "(password|secret|api_key)\s*=\s*[\"']" --include="*.py" .
grep -rE "execute\(.*%|text\(.*\+" --include="*.py" .
grep -rE "subprocess|shell=True|eval\(|exec\(" --include="*.py" .
```

---

## Authentication & Authorization

### If PR touches auth code:

- [ ] **Password handling** uses bcrypt/argon2 (via fastapi-users)
- [ ] **JWT tokens** have reasonable expiration
- [ ] **Protected endpoints** use `Depends(get_current_user)`
- [ ] **Admin endpoints** use `Depends(current_superuser)`

### If PR adds new endpoints:

```python
# REQUIRED on all non-public endpoints
@router.get("/endpoint")
async def endpoint(user: User = Depends(get_current_user)):
    ...
```

---

## Data Access (IDOR Prevention)

### If PR queries database:

- [ ] Queries filter by `user_id` for user-owned resources
- [ ] No global queries without authorization checks
- [ ] Admin queries explicitly check superuser status

```python
# BAD - No user scoping
job = await job_repo.get(job_id)

# GOOD - User scoped
job = await job_repo.get_by_user(job_id, user.id)
# or
job = await job_repo.get(job_id)
if job.user_id != user.id:
    raise HTTPException(404, "Not found")
```

---

## Input Validation

### If PR accepts user input:

- [ ] Input validated with Pydantic models
- [ ] String fields have `max_length` constraints
- [ ] Numeric fields have `ge`/`le` constraints
- [ ] Enums used for fixed choices
- [ ] No raw user input in SQL queries

```python
# GOOD - Pydantic validation
class JobCreate(BaseModel):
    prompt: str = Field(..., max_length=5000)
    input_file_key: str = Field(..., max_length=255)
    model_name: str = Field(default="gpt-4o-mini", max_length=50)
```

---

## SQL & Database

### If PR has database operations:

- [ ] Uses SQLAlchemy ORM (not raw SQL)
- [ ] No string formatting in queries
- [ ] No `text()` with user input
- [ ] Parameterized queries if raw SQL needed

```python
# BAD - SQL Injection risk
query = text(f"SELECT * FROM jobs WHERE id = '{job_id}'")

# GOOD - Parameterized
query = select(Job).where(Job.id == job_id)
```

---

## LLM & Prompts

### If PR touches LLM code:

- [ ] User input validated before prompt construction
- [ ] `max_tokens` configured (not unbounded)
- [ ] No secrets in prompts
- [ ] Prompts not logged at INFO level
- [ ] Output validated/sanitized before storage

```python
# GOOD - Bounded LLM call
response = await client.complete(
    prompt=sanitized_prompt,
    max_tokens=1500,  # Always set
)
```

---

## File Operations

### If PR handles file uploads:

- [ ] File size limit enforced
- [ ] File type validated (MIME type, not just extension)
- [ ] Filename sanitized (no path traversal)
- [ ] Files stored in user-scoped paths

```python
# GOOD - Sanitized filename
import os
safe_filename = os.path.basename(filename)  # Remove path components
safe_filename = safe_filename.replace("..", "")  # Extra safety
```

### If PR handles file downloads:

- [ ] User can only download their own files
- [ ] Presigned URLs have short expiry
- [ ] No path traversal in file keys

---

## Secrets & Configuration

### If PR adds configuration:

- [ ] Secrets from environment variables (`os.environ`)
- [ ] No hardcoded secrets/credentials
- [ ] Secrets not logged
- [ ] `.env.example` updated (with placeholder values)

```python
# BAD
api_key = "sk-abc123..."

# GOOD
api_key = os.environ["OPENAI_API_KEY"]
```

---

## Error Handling

### If PR adds error handling:

- [ ] Error messages don't expose internals
- [ ] Stack traces not returned to users
- [ ] Sensitive data not in error messages

```python
# BAD - Exposes internals
raise HTTPException(500, f"Database error: {str(e)}")

# GOOD - Generic message
logger.error(f"Database error: {e}")
raise HTTPException(500, "Internal server error")
```

---

## Logging

### If PR adds logging:

- [ ] No secrets in log messages
- [ ] No full prompts at INFO level (DEBUG only)
- [ ] No PII in logs (or properly masked)
- [ ] Security events logged (auth failures, etc.)

```python
# BAD
logger.info(f"Processing with key: {api_key}")

# GOOD
logger.info("Processing job", extra={"job_id": job_id})
```

---

## Dependencies

### If PR adds dependencies:

- [ ] Dependency is actively maintained
- [ ] No known vulnerabilities (check `pip-audit`)
- [ ] Version pinned in `pyproject.toml`
- [ ] License compatible with project

```bash
# Check new dependency
pip-audit --require-hashes
pip show <package>  # Check last update
```

---

## Docker/Deployment

### If PR modifies Docker/deployment:

- [ ] No secrets in Dockerfile
- [ ] No secrets in docker-compose (use env_file)
- [ ] Base image version pinned
- [ ] Runs as non-root user

```dockerfile
# BAD
ENV SECRET_KEY=hardcoded-secret

# GOOD
# SECRET_KEY passed via environment at runtime
```

---

## Quick Copy-Paste Checklist

```markdown
## Security Review

### General
- [ ] No hardcoded secrets
- [ ] No SQL injection vectors
- [ ] No command injection vectors

### If touches auth/data:
- [ ] Proper auth dependency on endpoints
- [ ] User-scoped data access (IDOR prevention)
- [ ] Input validated with Pydantic

### If touches LLM:
- [ ] max_tokens configured
- [ ] Prompts not logged at INFO
- [ ] Output validated

### If touches files:
- [ ] Size limits enforced
- [ ] Type validated
- [ ] Filename sanitized

### CI/CD
- [ ] ./scripts/quick-scan.sh passes
- [ ] pip-audit clean
```

---

## PR Template Addition

Add to `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Security Checklist

- [ ] I have run `./scripts/quick-scan.sh` with no critical findings
- [ ] This PR does not introduce hardcoded secrets
- [ ] If this PR adds endpoints, they have proper authentication
- [ ] If this PR handles user input, it is validated with Pydantic
- [ ] If this PR queries data, it filters by user_id where appropriate
```

---

## References

- Main methodology: `SKILL.md`
- Test payloads: `references/test-payloads.md`
- Auth security: `references/auth-security-checklist.md`
- Database security: `references/database-security-checklist.md`
