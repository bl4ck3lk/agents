# FastAPI Security Checklist

Security assessment for FastAPI application in the Agents platform.

## Overview

This checklist covers FastAPI-specific security considerations including routing, middleware, dependencies, and request/response handling.

## Middleware Security

### Security Headers

**Check Points:**
- [ ] X-Content-Type-Options: nosniff
- [ ] X-Frame-Options: DENY
- [ ] Content-Security-Policy: default-src 'self'
- [ ] Strict-Transport-Security: max-age=31536000
- [ ] Referrer-Policy: strict-origin-when-cross-origin
- [ ] Permissions-Policy: geolocation=(), microphone=(), camera=()

**Search Patterns:**
```bash
# Security headers in middleware
Grep: X-Content-Type|X-Frame-Options|CSP|HSTS
Path: agents/api/

# Custom middleware
Grep: @app\.middleware|add_middleware|Middleware
Path: agents/api/app.py
```

**Implementation:**
```python
# Add custom middleware for security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

---

## CORS Configuration

### Check Points

- [ ] CORS origins restricted to specific domains (not `*`)
- [ ] Credentials only enabled for trusted origins
- [ ] Allowed methods restricted (not all methods)
- [ ] Allowed headers restricted (not all headers)
- [ ] Preflight requests handled correctly

**Search Patterns:**
```bash
# CORS configuration
Grep: CORSMiddleware|allow_origins|allow_credentials|allow_methods
Path: agents/api/app.py

# Dangerous wildcard (BAD in production)
Grep: allow_origins.*\*|allow_origins.*\["\*"
Path: agents/api/app.py
```

**Test Cases:**
```bash
# Test CORS from unauthorized origin
curl -X OPTIONS http://localhost:8000/jobs \
  -H "Origin: http://evil.com" \
  -H "Access-Control-Request-Method: POST"

# Expected: No Access-Control-Allow-Origin header (or specific allowed domain)
```

---

## Authentication & Authorization

### Dependency Injection for Auth

**Check Points:**
- [ ] All protected endpoints use `Depends()` for auth
- [ ] Admin endpoints use `Depends(current_superuser)`
- [ ] User-specific endpoints validate ownership
- [ ] No public endpoints that should be protected

**Search Patterns:**
```bash
# Auth dependency usage
Grep: Depends\(get_current_user|Depends\(current_active_user|Depends\(current_superuser
Path: agents/api/routes/

# Missing auth on sensitive endpoints (potential vulnerability)
Grep: @router\.(get|post|put|delete|patch).*job|@router\.(get|post|put|delete|patch).*api.key
Path: agents/api/routes/
```

### JWT Token Security

**Check Points:**
- [ ] JWT algorithm is HS256 or RS256 (not `none`)
- [ ] JWT secret is sufficiently long (32+ chars)
- [ ] Token expiration is configured (not infinite)
- [ ] Token signature is validated on every request

**Search Patterns:**
```bash
# JWT configuration
Grep: algorithm|SECRET_KEY|jwt_secret|decode.*verify
Path: agents/api/auth/

# Token expiration
Grep: timedelta|expire|access_token|refresh_token|lifetime
Path: agents/api/auth/
```

**Test Cases:**
```python
# Test 1: JWT algorithm bypass
# Decode JWT, change "alg" to "none", remove signature
# Send modified token
# Expected: 401 Unauthorized

# Test 2: JWT expiration
# Use expired token
# Expected: 401 Unauthorized

# Test 3: Token replay
# Use same token multiple times
# Expected: Works (if not revoked) - implement token revocation if needed
```

---

## Rate Limiting

### Implementation Check

**Check Points:**
- [ ] Rate limiting configured on sensitive endpoints
- [ ] Per-user rate limiting (not just per-IP)
- [ ] Rate limit errors handled gracefully
- [ ] Different limits for different operations

**Search Patterns:**
```bash
# Rate limiting decorator
Grep: @limiter\.limit|slowapi|RateLimiter
Path: agents/api/routes/

# Rate limit configuration
Grep: "*/minute|per.*hour|limit"
Path: agents/api/routes/
```

**Current Implementation Check:**
```bash
# Check rate limits on job creation
Grep -A2 "@router.*post.*job" agents/api/routes/jobs.py | grep limiter

# Check rate limits on file upload
Grep -A2 "@router.*post.*upload" agents/api/routes/files.py | grep limiter
```

**Test Cases:**
```bash
# Test rate limiting
for i in {1..30}; do
  curl -X POST http://localhost:8000/jobs \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"input_file_key": "test.csv", "prompt": "test"}'
done

# Expected: After 20 requests (or configured limit), get 429 Too Many Requests
```

---

## Input Validation

### Pydantic Models

**Check Points:**
- [ ] All request bodies use Pydantic models
- [ ] Field constraints defined (min_length, max_length, regex)
- [ ] Custom validators for complex validation
- [ ] No manual validation scattered in route handlers

**Search Patterns:**
```bash
# Pydantic model usage
Grep: request:.*Request|response_model=|BaseModel
Path: agents/api/routes/

# Field constraints
Grep: Field\(.*min|Field\(.*max|Field\(.*regex|Field\(.*pattern
Path: agents/api/schemas.py

# Custom validators
Grep: @validator|@field_validator
Path: agents/api/schemas.py
```

**Vulnerable Pattern:**
```python
# BAD: No validation
async def create_job(body: dict):
    return process_job(body)

# GOOD: Pydantic validation
async def create_job(job: JobCreate):
    return process_job(job)
```

---

## Error Handling

### Check Points

- [ ] Errors don't expose stack traces
- [ ] Sensitive data not in error messages
- [ ] Error responses follow consistent format
- [ ] HTTPException used appropriately

**Search Patterns:**
```bash
# Error handling
Grep: HTTPException|raise.*Exception|try:.*except
Path: agents/api/routes/

# Stack trace exposure
Grep: traceback|exc_info|debug=True
Path: agents/api/routes/
```

**Vulnerable Pattern:**
```python
# BAD: Exposes stack trace
@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    try:
        return get_job_by_id(job_id)
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

# GOOD: Safe error message
@app.get("/jobs/{job_id}")
async def get_job(job_id: str, user: User = Depends(get_current_user)):
    try:
        return get_job_by_id(job_id, user.id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Job not found")
```

---

## Path Parameter Validation

### Check Points

- [ ] Path parameters validated (type, length, format)
- [ ] UUID validation for ID parameters
- [ ] No injection via path parameters

**Search Patterns:**
```bash
# Path parameter definitions
Grep: Path\(.*id|Query\(.*id|path:.*str
Path: agents/api/routes/

# UUID validation
Grep: UUID|uuid.*validate|check.*uuid
Path: agents/api/
```

**Test Cases:**
```python
# Test 1: Path traversal
GET /api/jobs/../../etc/passwd
# Expected: 404 (validation rejects)

# Test 2: SQL injection via path
GET /api/jobs/1'; DROP TABLE users;--
# Expected: 404 or 400 (validation rejects)

# Test 3: Invalid UUID
GET /api/jobs/not-a-uuid
# Expected: 422 (validation error)
```

---

## OpenAPI Documentation Security

### Check Points

- [ ] Sensitive endpoints not documented in production
- [ ] No example credentials in API docs
- [ ] Authentication required clearly documented
- [ ] Sensitive data not in example responses

**Search Patterns:**
```bash
# OpenAPI configuration
Grep: openapi_tags|docs_url|redoc_url|include_in_schema
Path: agents/api/app.py

# Hide endpoints from docs
Grep: include_in_schema=False
Path: agents/api/routes/
```

**Recommendations:**

```python
# Hide internal endpoints from docs
@app.post("/internal/task", include_in_schema=False)
async def internal_task():
    pass

# Clear authentication tags
app = FastAPI(
    openapi_tags=[
        {"name": "Jobs", "description": "Job management (requires auth)"},
    ]
)
```

---

## Dependency Injection

### Check Points

- [ ] Dependencies properly scoped (request-scoped vs app-scoped)
- [ ] No circular dependencies
- [ ] Database sessions managed correctly

**Search Patterns:**
```bash
# FastAPI dependencies
Grep: Depends\(get_async_session|Depends\(get_db|get_session
Path: agents/api/routes/

# Session management
Grep: async with.*session|sessionmaker|AsyncSession
Path: agents/api/
```

---

## Async/Await Security

### Check Points

- [ ] All I/O operations use async/await
- [ ] No blocking calls in async functions
- [ ] Proper error handling in async contexts

**Search Patterns:**
```bash
# Async function definitions
Grep: async def |await
Path: agents/api/routes/

# Blocking calls in async (BAD)
Grep: time\.sleep|requests\.get|subprocess\.run
Path: agents/api/routes/  # Should use asyncio.sleep, httpx.AsyncClient
```

---

## WebSocket Security (if applicable)

### Check Points

- [ ] Authentication on WebSocket connection
- [ ] Message validation
- [ ] Rate limiting on WebSocket messages
- [ ] Secure connection (wss:// in production)

**Note:** WebSocket endpoints not currently implemented in the Agents platform.

---

## Quick FastAPI Security Scan

```bash
# Run all FastAPI security checks
echo "=== FastAPI Security Scan ===" && \
echo "\n--- Security Headers ---" && \
grep -rE "X-Content-Type|X-Frame-Options|CSP|HSTS" agents/api/ && echo "Review headers" || echo "Add security headers middleware" && \
echo "\n--- CORS Configuration ---" && \
grep -rE "allow_origins.*\*" agents/api/ && echo "WARN: Wildcard CORS" || echo "OK" && \
echo "\n--- Missing Auth on Jobs ---" && \
grep -B2 "@router\.(get|post|delete).*job" agents/api/routes/jobs.py | grep -v "Depends" && echo "WARN: Missing auth" || echo "OK" && \
echo "\n--- Rate Limiting ---" && \
grep -r "@limiter\.limit" agents/api/routes/ && echo "OK" || echo "Add rate limiting"
```

## Priority Summary

| # | Area | Priority | Status |
|---|-------|----------|--------|
| 1 | Security Headers | P2 | [ ] |
| 2 | CORS Configuration | P1 | [ ] |
| 3 | Auth Dependencies | P0 | [ ] |
| 4 | JWT Token Security | P0 | [ ] |
| 5 | Rate Limiting | P1 | [ ] |
| 6 | Input Validation | P0 | [ ] |
| 7 | Error Handling | P1 | [ ] |
| 8 | Path Validation | P1 | [ ] |
| 9 | Dependency Injection | P2 | [ ] |
| 10 | Async/Await Safety | P2 | [ ] |

## References

- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [FastAPI - Security](https://fastapi.tiangolo.com/tutorial/security/)
