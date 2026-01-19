# Purple Hat - Quick Reference

Quick reference guide for security assessment of Agents LLM batch processing platform.

## Search Patterns Legend

```
Grep: pattern1|pattern2
Path: directory/
```

Translates to: `grep -rE "pattern1|pattern2" directory/`

---

## Critical Security Commands

### Quick Security Scan
```bash
./scripts/quick-scan.sh
```

### LLM Security Scan
```bash
./scripts/llm-security-scan.sh
```

### Secrets Scan
```bash
./scripts/secrets-scan.sh
```

### Dependency Audit
```bash
uv pip list --outdated
pip-audit
```

---

## OWASP Top 10 2021 - Quick Checks

| # | Risk | Quick Check | Command |
|---|-------|-------------|---------|
| A01 | Broken Access Control | IDOR on jobs/api keys | `grep "Depends(current" agents/api/routes/` |
| A02 | Cryptographic Failures | Hardcoded secrets | `grep "api_key.*=" agents/ | grep -v env` |
| A03 | Injection | SQL/command injection | `grep "execute(\|subprocess" agents/` |
| A05 | Security Misconfiguration | Debug mode enabled | `grep "DEBUG.*True" docker-compose.yml` |
| A06 | Vulnerable Components | Outdated dependencies | `uv pip list --outdated` |
| A07 | Authentication Failures | Weak passwords | Check password hashing in auth |
| A10 | SSRF | URL input validation | `grep "http://.*input" agents/` |

---

## OWASP LLM Top 10 2025 - Quick Checks

| # | Risk | Quick Check | Command |
|---|-------|-------------|---------|
| LLM01 | Prompt Injection | User input in prompts | `grep "PromptTemplate" agents/core/` |
| LLM02 | Sensitive Info Disclosure | Prompt logging | `grep "logger.*prompt" agents/` |
| LLM03 | Supply Chain | Unpinned models | `grep "model.*=.*latest" agents/` |
| LLM04 | Data Poisoning | Output validation | `grep "extract_json" agents/core/` |
| LLM05 | Improper Output | max_tokens config | `grep "max_tokens" agents/core/llm_client.py` |
| LLM06 | Excessive Agency | Function calling | `grep "bind_tools" agents/core/` |
| LLM10 | Unbounded Consumption | File size limits | `grep "max_file_size" agents/api/` |

---

## FastAPI Security - Quick Checks

| Area | Check | Command |
|-------|--------|---------|
| Headers | Security headers present | `grep "X-Frame\|CSP" agents/api/` |
| CORS | Not wildcard | `grep "allow_origins.*\*" agents/api/app.py` |
| Auth | Dependencies on endpoints | `grep "Depends(current" agents/api/routes/` |
| Rate Limit | limiter decorator | `grep "@limiter.limit" agents/api/routes/` |
| Input Validation | Pydantic models | `grep "BaseModel" agents/api/schemas.py` |

---

## S3/MinIO Security - Quick Checks

| Area | Check | Command |
|-------|--------|---------|
| Presigned URL | Expiry configured | `grep "S3_PRESIGNED_EXPIRY" .env.example` |
| Bucket Access | Not public | `grep "anonymous set public" docker-compose.yml` |
| Credentials | Not hardcoded | `grep "MINIO_ROOT.*=" docker-compose.yml` |
| Uploads | Type validation | `grep "content_type" agents/api/routes/files.py` |
| Downloads | User-scoped | `grep "user_id" agents/api/routes/files.py` |

---

## Database Security - Quick Checks

| Area | Check | Command |
|-------|--------|---------|
| SQL Injection | No raw SQL | `grep "text(.*+|execute(.*%" agents/db/` |
| ORM Safety | Using SQLAlchemy | `grep "select(\|insert(\|update(" agents/db/` |
| Row Security | user_id filters | `grep "where.*user_id" agents/api/routes/` |
| Connection | TLS enabled | `grep "sslmode" DATABASE_URL` |

---

## Container Security - Quick Checks

| Area | Check | Command |
|-------|--------|---------|
| Base Image | Version pinned | `grep "^FROM" Dockerfile` |
| Non-root | USER directive | `grep "^USER" Dockerfile` |
| Multi-stage | COPY --from= | `grep "COPY --from=" Dockerfile` |
| Credentials | Not in image | `grep "ENV.*SECRET" Dockerfile` |

---

## CI/CD Security - Quick Checks

| Area | Check | Command |
|-------|--------|---------|
| Actions Pinned | Full SHA | `grep "uses:.*@" .github/workflows/*.yml` |
| Secrets | Not in workflows | `grep "secret.*=" .github/workflows/*.yml` |
| Permissions | Minimal GITHUB_TOKEN | `grep "permissions:" .github/workflows/*.yml` |

---

## Priority Fixes

### P0 (Critical - Fix Immediately)

1. **Hardcoded secrets in code**
   - Search: `grep -rE "(api_key|secret)\s*=\s*[\"'][^$\{]" agents/`
   - Fix: Use environment variables

2. **SQL injection vulnerabilities**
   - Search: `grep -rE "text\(.*\+|execute\(.*%" agents/db/`
   - Fix: Use SQLAlchemy ORM with parameterized queries

3. **Missing authentication**
   - Search: `grep -B2 "@router\.(get|post|delete)" agents/api/routes/ | grep -v "Depends"`
   - Fix: Add `Depends(get_current_user)`

4. **Prompt injection risk**
   - Search: `grep "PromptTemplate.*render" agents/core/`
   - Fix: Validate user input before prompt construction

5. **IDOR vulnerabilities**
   - Search: Check job/API key endpoints without user_id filtering
   - Fix: Add ownership validation

### P1 (High - Fix Soon)

1. **Default credentials in production**
   - Search: `grep "minioadmin" docker-compose.yml`
   - Fix: Use environment variables for production

2. **Missing rate limiting**
   - Search: `grep -r "@limiter\.limit" agents/api/routes/`
   - Fix: Add `@limiter.limit` decorator to sensitive endpoints

3. **Debug mode enabled**
   - Search: `grep "DEBUG.*True" docker-compose.yml`
   - Fix: Set DEBUG=False in production

4. **CORS wildcard**
   - Search: `grep "allow_origins.*\*" agents/api/app.py`
   - Fix: Specify allowed origins

5. **File upload validation**
   - Search: Check file upload endpoints for type/size limits
   - Fix: Add MIME type validation and size limits

### P2 (Medium - Review Soon)

1. **Outdated dependencies**
   - Search: `uv pip list --outdated`
   - Fix: Update packages, review CVEs

2. **Missing security headers**
   - Search: `grep "X-Content-Type\|X-Frame-Options" agents/api/`
   - Fix: Add security headers middleware

3. **Presigned URL expiry**
   - Search: Check S3_PRESIGNED_EXPIRY value
   - Fix: Set reasonable expiry (5-15 minutes)

4. **No S3 bucket encryption**
   - Search: Check if encryption at rest enabled
   - Fix: Enable S3 SSE-S3 or SSE-KMS

---

## Test Commands

### Test Authentication
```bash
# Login
curl -X POST http://localhost:8002/auth/jwt/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password"

# Use token
curl http://localhost:8002/jobs \
  -H "Authorization: Bearer $TOKEN"
```

### Test Rate Limiting
```bash
# Send 30 requests (check configured limit)
for i in {1..30}; do
  curl -X POST http://localhost:8002/jobs \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"input_file_key": "test.csv", "prompt": "test"}'
done

# Expected: 429 Too Many Requests after limit
```

### Test File Upload
```bash
# Upload file
curl -X POST http://localhost:8002/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.csv", "content_type": "text/csv"}'

# Then upload to presigned URL returned
```

### Test SQL Injection
```bash
# Try injection in job creation
curl -X POST http://localhost:8002/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "test'; DROP TABLE web_jobs;--"}'

# Expected: 422 validation error or 500 (if vulnerable)
```

---

## Common Vulnerability Patterns

### Vulnerable: Mass Assignment
```python
# BAD
user.update(**request.model_dump())

# GOOD
user.update(
    name=data.name,
    email=data.email
)
```

### Vulnerable: Unvalidated Input
```python
# BAD
async def process(query: str):
    return llm.complete(query)

# GOOD
async def process(query: Annotated[str, Field(max_length=500)]):
    return llm.complete(query)
```

### Vulnerable: No Auth Check
```python
# BAD
@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    return get_job_by_id(job_id)

# GOOD
@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: User = Depends(get_current_user)):
    return get_job_by_id(job_id, user.id)
```

### Vulnerable: Directory Traversal
```python
# BAD
filename = request.filename
path = f"uploads/{filename}"

# GOOD
filename = sanitize_filename(request.filename)
path = f"uploads/{user_id}/{filename}"
```

---

## Security Tools

### Static Analysis
```bash
# Code quality
ruff check agents/
mypy agents/

# Security
bandit -r agents/
safety check
pip-audit
```

### Container Scanning
```bash
# Trivy (vulnerabilities)
trivy image agents:latest
trivy image --severity HIGH,CRITICAL agents:latest

# Hadolint (Dockerfile best practices)
hadolint Dockerfile

# Dockle (container security)
dockle agents:latest
```

### Dependency Analysis
```bash
# Outdated packages
uv pip list --outdated

# Known vulnerabilities
pip-audit
safety check

# License compliance
pip-licenses
```

---

## Reporting

### Security Report Template

```markdown
# Security Assessment Report - Agents Platform

**Date:** [DATE]
**Assessed By:** [NAME]
**Scope:** [Development/Staging/Production]

## Executive Summary

- Total Findings: [N]
- Critical: [N]
- High: [N]
- Medium: [N]
- Low: [N]

## Detailed Findings

### [Critical/High/Medium/Low] - [Vulnerability Name]

**Component:** [File/Endpoint]
**Risk:** [Description of impact]
**PoC:** [Proof of concept or payload]
**Remediation:**
1. [Fix step 1]
2. [Fix step 2]

## Recommendations

1. [Priority 1 recommendation]
2. [Priority 2 recommendation]
3. [Priority 3 recommendation]
```

---

## References

- Main methodology: `SKILL.md`
- LLM security: `references/llm-security-checklist.md`
- FastAPI security: `references/fastapi-security-checklist.md`
- S3 security: `references/s3-security-checklist.md`
- Test payloads: `references/test-payloads.md`
