# API Security Checklist

Security assessment for API endpoints in the Agents platform.

## OWASP API Security Top 10 2023

### API1:2023 - Broken Object Level Authorization (BOLA)

**Check Points:**
- [ ] Every endpoint accessing data by ID validates user ownership
- [ ] UUIDs used instead of sequential IDs where possible
- [ ] Authorization checks happen at data layer, not just route
- [ ] Bulk operations validate all object ownership
- [ ] Same error response for "not found" and "not authorized"

**Search Patterns:**
```bash
# Job endpoints
Grep: @router\.(get|delete).*job_id|async def.*job.*\(job_id
Path: agents/api/routes/jobs.py

# API key endpoints
Grep: @router\.(get|delete).*key_id|async def.*key.*\(key_id
Path: agents/api/routes/api_keys.py

# Ownership validation
Grep: user_id.*==|where.*user_id|current_user\.id
Path: agents/api/routes/
```

**Test Cases:**
```python
# Test 1: Access another user's job
GET /api/jobs/{OTHER_USER_JOB_UUID}
Authorization: Bearer YOUR_TOKEN
# Expected: 404 (not found) or 403 (forbidden)

# Test 2: Modify another user's job
PATCH /api/jobs/{YOUR_JOB_UUID}
Authorization: Bearer YOUR_TOKEN
{"user_id": "OTHER_USER_UUID"}
# Expected: 403 (validation rejects user_id modification)

# Test 3: Access all API keys (admin check required)
GET /api/api-keys
Authorization: Bearer REGULAR_USER_TOKEN
# Expected: Only return YOUR keys, not all users' keys
```

---

### API2:2023 - Broken Authentication

**Check Points:**
- [ ] Strong password policy enforced (fastapi-users)
- [ ] Brute force protection (rate limiting on login)
- [ ] Secure token storage (httpOnly, Secure cookies if using sessions)
- [ ] Token expiration configured appropriately
- [ ] Password hashing uses bcrypt

**Search Patterns:**
```bash
# Token configuration
Grep: lifetime|expire|ttl|access_token|refresh_token
Path: agents/api/auth/

# Rate limiting on auth
Grep: @limiter\.limit.*login|@limiter\.limit.*auth
Path: agents/api/auth/

# Password hashing
Grep: bcrypt|passlib|password_hash
Path: agents/api/auth/
```

---

### API3:2023 - Broken Object Property Level Authorization

**Check Points:**
- [ ] Response models exclude sensitive fields (password_hash, api_key)
- [ ] Mass assignment protection (explicit field allowlists)
- [ ] Admin-only fields not modifiable by regular users
- [ ] Read-only fields enforced (created_at, id, user_id)

**Search Patterns:**
```bash
# Field exclusion in responses
Grep: response_model_exclude|exclude=|Field\(.*exclude
Path: agents/api/routes/

# Mass assignment patterns
Grep: model_dump\(\*\*dict|update\(.*model_dump
Path: agents/api/routes/

# Admin-only fields
Grep: is_admin|is_superuser|role
Path: agents/api/schemas.py
```

**Test Cases:**
```python
# Test 1: Mass assignment to escalate privileges
PATCH /api/users/me
Authorization: Bearer REGULAR_USER_TOKEN
{"is_superuser": true}
# Expected: 403 or field ignored

# Test 2: Modify read-only field
PATCH /api/jobs/{JOB_ID}
Authorization: Bearer YOUR_TOKEN
{"created_at": "2024-01-01", "user_id": "other-user"}
# Expected: Fields ignored or rejected
```

---

### API4:2023 - Unrestricted Resource Consumption

**Check Points:**
- [ ] Rate limiting on all endpoints
- [ ] Pagination with max limit enforced (e.g., max 100)
- [ ] Request body size limits
- [ ] File upload size limits
- [ ] Job unit count limits

**Search Patterns:**
```bash
# Rate limiting
Grep: @limiter\.limit|RateLimiter|slowapi
Path: agents/api/routes/

# Pagination limits
Grep: limit.*=|max_limit|page_size|Query\(.*le=
Path: agents/api/routes/

# Request size limits
Grep: max_size|body_limit|MAX_CONTENT_LENGTH
Path: agents/api/

# File upload limits
Grep: max_file_size|MAX_UPLOAD
Path: agents/api/routes/files.py
```

**Recommended Limits:**
```python
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20
RATE_LIMIT_PER_MINUTE = 60
MAX_FILE_SIZE_MB = 100
MAX_JOB_UNITS = 100000
```

---

### API5:2023 - Broken Function Level Authorization

**Check Points:**
- [ ] Admin endpoints require admin authentication
- [ ] Sensitive operations require re-authentication
- [ ] HTTP method restrictions enforced per endpoint
- [ ] Function-level permissions documented

**Search Patterns:**
```bash
# Admin checks
Grep: Depends\(current_superuser|is_superuser|admin_required
Path: agents/api/routes/admin.py

# Admin router
Grep: @router.*admin|prefix.*admin
Path: agents/api/routes/
```

**Test Cases:**
```python
# Test: Access admin endpoint as regular user
GET /admin/users
Authorization: Bearer REGULAR_USER_TOKEN
# Expected: 403 Forbidden
```

---

### API6:2023 - Unrestricted Access to Sensitive Business Flows

**Check Points:**
- [ ] Job creation has rate limits
- [ ] CAPTCHA on high-value operations (if applicable)
- [ ] Anti-automation measures on job creation
- [ ] Job result download has rate limits

**Search Patterns:**
```bash
# Rate limits on jobs
Grep: @limiter\.limit.*job|create.*job.*limit
Path: agents/api/routes/jobs.py

# Rate limits on downloads
Grep: @limiter\.limit.*download|results.*limit
Path: agents/api/routes/files.py
```

---

### API7:2023 - Server Side Request Forgery (SSRF)

**Check Points:**
- [ ] URL validation for LLM API base_url parameter
- [ ] Allowlist for LLM provider domains
- [ ] Block internal/private IP ranges
- [ ] Block cloud metadata endpoints

**Search Patterns:**
```bash
# URL fetching (LLM APIs)
Grep: base_url|endpoint|http://|https://
Path: agents/core/llm_client.py agents/cli.py

# User-controlled URLs
Grep: f"http|\.format\(.*url|url.*\+
Path: agents/core/llm_client.py
```

**Test Cases:**
```python
# Test 1: Internal network access
POST /jobs
{
  "base_url": "http://localhost:8001/internal-admin"
}

# Test 2: Cloud metadata
POST /jobs
{
  "base_url": "http://169.254.169.254/latest/meta-data/"
}

# Expected: 400 (URL validation rejects)
```

---

### API8:2023 - Security Misconfiguration

**Check Points:**
- [ ] Debug mode disabled in production
- [ ] Security headers configured
- [ ] CORS properly restricted
- [ ] Default credentials changed
- [ ] Error messages don't leak stack traces
- [ ] API docs not exposing sensitive data

**Search Patterns:**
```bash
# Debug mode
Grep: DEBUG.*=.*True|--reload
Path: agents/ docker-compose*.yml

# Security headers
Grep: X-Content-Type|X-Frame-Options|CSP|HSTS
Path: agents/api/

# Verbose errors
Grep: traceback|stack_trace|exc_info
Path: agents/api/routes/
```

---

### API9:2023 - Improper Inventory Management

**Check Points:**
- [ ] API versioning documented
- [ ] Deprecated endpoints marked
- [ ] No undocumented endpoints
- [ ] Debug/test endpoints disabled in production

**Search Patterns:**
```bash
# Find all endpoints
Grep: @router\.(get|post|put|delete|patch)
Path: agents/api/routes/

# Hidden from docs
Grep: include_in_schema=False
Path: agents/api/routes/

# Version prefixes
Grep: /v1/|/v2/|APIRouter.*prefix
Path: agents/api/
```

---

### API10:2023 - Unsafe Consumption of APIs

**Check Points:**
- [ ] LLM provider responses validated
- [ ] TLS verification enabled for LLM APIs
- [ ] Timeouts configured on LLM API calls
- [ ] No secrets in URL parameters

**Search Patterns:**
```bash
# External API calls
Grep: openai\.|anthropic\.|requests\(|httpx\.
Path: agents/core/llm_client.py

# TLS verification disabled (DANGEROUS)
Grep: verify=False|ssl=False
Path: agents/core/

# Timeouts
Grep: timeout=|Timeout\(
Path: agents/core/llm_client.py
```

---

## Quick API Security Scan

```bash
# Run all API security checks
echo "=== API Security Scan ===" && \
echo "\n--- BOLA/IDOR Checks ---" && \
grep -rE "async def.*job.*\(job_id" agents/api/routes/jobs.py | grep -v "user_id" && echo "WARN: Missing ownership check" || echo "OK" && \
echo "\n--- Rate Limiting ---" && \
grep -r "@limiter\.limit" agents/api/routes/ && echo "OK" || echo "WARN: Add rate limiting" && \
echo "\n--- Debug Mode ---" && \
grep -rE "DEBUG.*True|RELOAD.*true" docker-compose*.yml && echo "WARN: Debug mode enabled" || echo "OK"
```

## Priority Summary

| # | Risk | Priority | Status |
|---|-------|----------|--------|
| 1 | BOLA/IDOR | P0 | [ ] |
| 2 | Rate Limiting | P0 | [ ] |
| 3 | Broken Auth | P1 | [ ] |
| 4 | SSRF | P1 | [ ] |
| 5 | Mass Assignment | P1 | [ ] |
| 6 | Resource Limits | P1 | [ ] |
| 7 | Function Level Auth | P1 | [ ] |
| 8 | Security Misconfig | P2 | [ ] |
| 9 | Inventory Mgmt | P2 | [ ] |
| 10 | Unsafe API Consumption | P2 | [ ] |

## References

- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [API Security Best Practices](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
