# Authentication Security Checklist

Security assessment for authentication system in the Agents platform.

## fastapi-users Implementation

### Password Policy

**Check Points:**
- [ ] Minimum password length (fastapi-users default: 8)
- [ ] Password complexity requirements
- [ ] Password hashed with bcrypt
- [ ] No plaintext password storage

**Search Patterns:**
```bash
# Password hashing
Grep: bcrypt|PasswordHasher|password_hash
Path: agents/api/auth/

# Password validation
Grep: password.*min_length|password.*max_length|password.*policy
Path: agents/api/auth/
```

### JWT Token Configuration

**Check Points:**
- [ ] JWT algorithm is HS256 (or RS256)
- [ ] JWT secret is 32+ characters
- [ ] Access token expiration configured (default: 15-30 minutes)
- [ ] Refresh token expiration configured (default: 30 days)
- [ ] Tokens signed with SECRET_KEY from environment

**Search Patterns:**
```bash
# JWT algorithm and configuration
Grep: HS256|RS256|jwt_secret|SECRET_KEY|algorithm
Path: agents/api/auth/backend.py agents/api/auth/config.py

# Token expiration
Grep: timedelta|minutes=|days=|lifetime|expire
Path: agents/api/auth/config.py
```

### Rate Limiting on Auth

**Check Points:**
- [ ] Login endpoint rate limited
- [ ] Registration endpoint rate limited
- [ ] Password reset rate limited
- [ ] Brute force protection implemented

**Search Patterns:**
```bash
# Rate limiting on auth endpoints
Grep: @limiter\.limit.*login|@limiter\.limit.*register|@limiter\.limit.*reset
Path: agents/api/auth/ agents/api/routes/

# Account lockout (fastapi-users may not have this)
Grep: failed_attempts|lockout|account_lock
Path: agents/api/auth/
```

### OAuth Integration (if configured)

**Check Points:**
- [ ] OAuth secrets from environment
- [ ] OAuth callback URLs validated
- [ ] State parameter validated (CSRF protection)
- [ ] OAuth tokens stored securely

**Search Patterns:**
```bash
# OAuth configuration
Grep: GOOGLE_CLIENT|GITHUB_CLIENT|OAUTH|OAuth
Path: agents/api/auth/config.py .env.example

# OAuth secrets in code (BAD)
Grep: CLIENT_SECRET.*=.*['\"][^$\{]
Path: agents/api/auth/
```

---

## Session Management

### Token Storage

**Check Points:**
- [ ] Access tokens stored in memory (not localStorage for web)
- [ ] Refresh tokens stored securely (httpOnly cookie if using web)
- [ ] Token rotation on refresh
- [ ] Session invalidation on password change

**Current Implementation:** JWT-based (stateless)
- No server-side sessions
- Tokens validated on each request

### Token Refresh

**Check Points:**
- [ ] Refresh token endpoint available
- [ ] Old access token invalidated after refresh
- [ ] Refresh token one-time use (rotated)
- [ ] Refresh token expiration enforced

---

## User Management

### Registration

**Check Points:**
- [ ] Email verification required (if configured)
- [ ] Password policy enforced
- [ ] Rate limiting on registration
- [ ] No enumeration of existing emails

**Search Patterns:**
```bash
# Registration endpoint
Grep: register|UserCreate|POST.*register
Path: agents/api/auth/ agents/api/routes/

# Email verification
Grep: verify|is_verified|is_active
Path: agents/api/auth/
```

### Password Reset

**Check Points:**
- [ ] Secure token generation (cryptographically random)
- [ ] Token expiry configured (e.g., 1 hour)
- [ ] Token sent via secure channel (email)
- [ ] Rate limiting on password reset requests
- [ ] Password change invalidates all tokens

**Search Patterns:**
```bash
# Password reset
Grep: reset.*password|forgot|reset_token
Path: agents/api/auth/

# Token generation
Grep: generate.*token|create_token|uuid
Path: agents/api/auth/
```

---

## Multi-Tenancy (if applicable)

**Check Points:**
- [ ] User-scoped data access (user_id filtering)
- [ ] No cross-tenant data leakage
- [ ] Tenant isolation in database queries

**Search Patterns:**
```bash
# User scoping
Grep: user_id|current_user\.id|where.*user_id
Path: agents/api/routes/ agents/db/
```

---

## Two-Factor Authentication (2FA)

**Status:** Not currently implemented (optional feature)

**Recommendations for Future Implementation:**
- Use TOTP (Time-based One-Time Password)
- Support authenticator apps (Google Authenticator, Authy)
- Backup codes for recovery
- 2FA only for sensitive operations (not for all logins)

---

## Session Hijacking Prevention

### Check Points

- [ ] HTTPS enforced in production
- [ ] Secure flag on cookies (if using cookie-based auth)
- [ ] httpOnly flag on cookies (if using cookie-based auth)
- [ ] SameSite attribute on cookies
- [ ] CSRF protection (if using cookie-based auth)

**Search Patterns:**
```bash
# Cookie configuration
Grep: cookie|SameSite|httpOnly|Secure
Path: agents/api/

# HTTPS enforcement
Grep: HSTS|Strict-Transport-Security|https://
Path: agents/api/app.py
```

---

## Common Authentication Vulnerabilities

### Credential Stuffing

**Check Points:**
- [ ] Rate limiting prevents automated login attempts
- [ ] Account lockout after N failed attempts
- [ ] CAPTCHA on login (optional)

### Session Fixation

**Check Points:**
- [ ] Session tokens regenerated on login
- [ ] No session ID reuse

**Current Implementation:** JWT-based (no session IDs) - Not applicable

### Broken Access Control

**Check Points:**
- [ ] `Depends(get_current_user)` on protected endpoints
- [ ] `Depends(current_superuser)` on admin endpoints
- [ ] No bypass of auth checks

---

## Quick Auth Security Scan

```bash
# Run all authentication security checks
echo "=== Authentication Security Scan ===" && \
echo "\n--- Password Hashing ---" && \
grep -r "bcrypt|PasswordHasher" agents/api/auth/ && echo "OK" || echo "WARN: Check password hashing" && \
echo "\n--- JWT Configuration ---" && \
grep -r "SECRET_KEY|HS256|lifetime" agents/api/auth/ && echo "OK" || echo "WARN: Check JWT config" && \
echo "\n--- Rate Limiting on Login ---" && \
grep -r "@limiter\.limit.*login|@limiter\.limit.*auth" agents/api/ && echo "OK" || echo "WARN: Add login rate limiting" && \
echo "\n--- Auth Dependencies ---" && \
grep -r "Depends\(current" agents/api/routes/ && echo "OK" || echo "WARN: Missing auth on endpoints"
```

## Priority Summary

| # | Area | Priority | Status |
|---|-------|----------|--------|
| 1 | Password Hashing | P0 | [ ] |
| 2 | JWT Token Security | P0 | [ ] |
| 3 | Auth Dependencies | P0 | [ ] |
| 4 | Rate Limiting (Login) | P1 | [ ] |
| 5 | Rate Limiting (Register) | P1 | [ ] |
| 6 | Password Reset Security | P1 | [ ] |
| 7 | OAuth Configuration | P1 | [ ] |
| 8 | Session Management | P2 | [ ] |
| 9 | 2FA Support | P3 | [ ] |
| 10 | CSRF Protection | P2 | [ ] |

## References

- [fastapi-users Documentation](https://fastapi-users.github.io/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [OWASP Broken Authentication](https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/03-Identity_Management_Testing)
