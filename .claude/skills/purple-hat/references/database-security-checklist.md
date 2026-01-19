# Database Security Checklist

Security assessment for PostgreSQL database in the Agents platform.

## SQLAlchemy Security

### SQL Injection Prevention

**Check Points:**
- [ ] No raw SQL with string formatting
- [ ] All queries use SQLAlchemy ORM or parameterized queries
- [ ] User input never concatenated into SQL
- [ ] No dynamic table/column names from user input

**Search Patterns:**
```bash
# SQL Injection vectors (DANGEROUS)
Grep: text\(.*\+|text\(.*format|execute\(.*%|\.raw\(|f".*SELECT|f".*INSERT
Path: agents/db/

# Safe SQLAlchemy patterns (GOOD)
Grep: select\(|insert\(|update\(|\.where\(|\.filter\(
Path: agents/db/
```

**Vulnerable Pattern:**
```python
# BAD: String formatting (SQL injection risk)
session.execute(text(f"SELECT * FROM web_jobs WHERE id = {job_id}"))

# BAD: String concatenation
session.execute(text("SELECT * FROM web_jobs WHERE id = " + job_id))

# GOOD: Parameterized query
session.execute(text("SELECT * FROM web_jobs WHERE id = :job_id"), {"job_id": job_id})

# GOOD: ORM query
session.query(WebJob).filter(WebJob.id == job_id).first()
```

---

## Row-Level Security

### Check Points

- [ ] All queries filter by user_id (or tenant_id)
- [ ] No global queries without user scope
- [ ] API endpoints validate ownership before returning data
- [ ] Admin endpoints have explicit admin checks

**Search Patterns:**
```bash
# Missing user_id filter (potential vulnerability)
Grep: async def.*get.*\(|\.all\(\)|\.first\(\)
Path: agents/api/routes/

# Ownership validation patterns
Grep: where.*user_id|filter.*user_id|current_user\.id
Path: agents/api/routes/ agents/db/
```

**Vulnerable Pattern:**
```python
# BAD: No user scoping
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)):
    return session.query(WebJob).filter(WebJob.id == job_id).first()

# GOOD: User-scoped query
async def get_job(job_id: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    return session.query(WebJob).filter(WebJob.id == job_id, WebJob.user_id == user.id).first()
```

**Test Cases:**
```python
# Test: Access another user's job
GET /api/jobs/{OTHER_USER_JOB_UUID}
Authorization: Bearer YOUR_TOKEN

# Expected: 404 (not found) or 403 (forbidden)
```

---

## Connection Security

### Check Points

- [ ] SSL/TLS enabled for database connections
- [ ] Connection pooling configured
- [ ] Password not in connection string (use env var)
- [ ] Database credentials rotated regularly
- [ ] Connection timeout configured

**Search Patterns:**
```bash
# Database URL configuration
Grep: DATABASE_URL|postgresql://|sslmode|require
Path: .env.example docker-compose.yml

# Connection pooling
Grep: pool_size|max_overflow|pool_recycle|pool_pre_ping
Path: agents/db/

# Hardcoded credentials (BAD)
Grep: postgresql://.*:password@|postgres:postgres
Path: agents/ docker-compose.yml .env.example
```

**Secure Configuration:**
```bash
# GOOD: SSL enabled, credentials from env
DATABASE_URL=postgresql+asyncpg://user:${DB_PASSWORD}@host:5432/db?sslmode=require

# BAD: No SSL, hardcoded password
DATABASE_URL=postgresql://user:password123@host:5432/db
```

---

## Data Encryption

### Check Points

- [ ] Sensitive data encrypted at rest (if applicable)
- [ ] API keys encrypted in database
- [ ] Passwords hashed with bcrypt
- [ ] No plaintext secrets in database

**Search Patterns:**
```bash
# API key encryption
Grep: APIKeyEncryption|encrypt|decrypt|Fernet
Path: agents/api/

# Password hashing
Grep: bcrypt|PasswordHasher|hash_password|verify_password
Path: agents/api/auth/

# Plaintext secrets (BAD)
Grep: password_hash.*=.*['\"]|api_key.*=.*['\"]\s*[^$]
Path: agents/db/ agents/api/
```

---

## Database Schema Security

### Check Points

- [ ] No default passwords in schema migrations
- [ ] No hardcoded admin accounts in migrations
- [ ] Appropriate data types used (not TEXT for sensitive data)
- [ ] Foreign key constraints for referential integrity

**Search Patterns:**
```bash
# Migrations
Grep: CREATE USER|CREATE ROLE|DEFAULT.*password
Path: alembic/versions/

# Admin account creation
Grep: is_superuser.*=.*True|INSERT INTO users.*admin
Path: alembic/versions/ agents/db/
```

---

## Query Performance and DoS Prevention

### Check Points

- [ ] Query timeouts configured
- [ ] No unbounded queries (no LIMIT)
- [ ] Indexes on frequently queried columns
- [ ] No N+1 query problems

**Search Patterns:**
```bash
# Query limits
Grep: limit\(|LIMIT|\.first\(\)|\.all\(\)
Path: agents/api/routes/ agents/db/

# Query patterns that might be unbounded
Grep: session\.query\(|\.all\(\)
Path: agents/
```

---

## Migration Security

### Check Points

- [ ] Migration files don't contain sensitive data
- [ ] No test data in production migrations
- [ ] Migration rollback scripts tested
- [ ] Database user has minimal permissions (least privilege)

**Search Patterns:**
```bash
# Sensitive data in migrations
Grep: password|secret|api_key|INSERT INTO.*users.*admin
Path: alembic/versions/
```

---

## PostgreSQL-Specific Security

### Check Points

- [ ] PostgreSQL version updated and supported
- [ ] pg_hba.conf configured (if managing own server)
- [ ] Only trusted network access
- [ ] Logging enabled for audit trail

**Configuration (if self-hosted):**
```ini
# pg_hba.conf
# Require SSL for all connections
hostssl    all             all             0.0.0.0.0/0            md5

# Restrict to specific IPs
hostssl    all             all             10.0.0.0/8              md5

# No local password authentication
local      all             all                                     md5
```

---

## Backup Security

### Check Points

- [ ] Regular backups configured
- [ ] Backups encrypted
- [ ] Backups tested for restoration
- [ ] Backup access restricted
- [ ] Offsite backup storage

**Check:**
```bash
# Check backup scripts
Grep -r "backup\|pg_dump\|pg_restore" scripts/ .github/workflows/

# Check for backup configuration
Grep BACKUP|S3_BACKUP|backup_bucket
Path: .env.example docker-compose.yml
```

---

## Database Access Control

### Check Points

- [ ] Application user has minimal permissions (SELECT, INSERT, UPDATE, DELETE only)
- [ ] No GRANT ALL PRIVILEGES
- [ ] Separate read-only users for reporting (if applicable)
- [ ] Admin database access restricted

**Configuration:**
```sql
-- GOOD: Minimal permissions for app
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;

-- BAD: Excessive permissions
GRANT ALL PRIVILEGES ON DATABASE agents TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;
```

---

## Database Logging and Monitoring

### Check Points

- [ ] Query logging enabled in development
- [ ] Slow query logging configured
- [ ] Connection monitoring
- [ ] Failed login attempts logged (if using database auth)

**Configuration:**
```ini
# postgresql.conf
log_min_duration_statement = 1000  # Log queries > 1s
log_line_prefix = '%t [%p]: '
log_statement = 'all'  # All queries (development only!)
```

---

## Quick Database Security Scan

```bash
# Run all database security checks
echo "=== Database Security Scan ===" && \
echo "\n--- SQL Injection Vectors ---" && \
grep -rE "text\(.*\+|text\(.*format|execute\(.*%" agents/db/ && echo "WARN: SQL injection vectors" || echo "OK" && \
echo "\n--- ORM Usage ---" && \
grep -rE "select\(|insert\(|\.where\(" agents/db/ && echo "OK: Using ORM" || echo "WARN: Check query methods" && \
echo "\n--- User Scoping ---" && \
grep -rE "where.*user_id|filter.*user_id" agents/api/routes/ && echo "OK" || echo "WARN: Missing user_id filters" && \
echo "\n--- API Key Encryption ---" && \
grep -r "APIKeyEncryption|Fernet" agents/api/ && echo "OK" || echo "WARN: No API key encryption" && \
echo "\n--- Hardcoded DB Credentials ---" && \
grep -rE "postgresql://.*:password@|postgres:postgres" agents/ docker-compose.yml && echo "WARN: Hardcoded credentials" || echo "OK"
```

## Priority Summary

| # | Area | Priority | Status |
|---|-------|----------|--------|
| 1 | SQL Injection Prevention | P0 | [ ] |
| 2 | Row-Level Security (user_id filters) | P0 | [ ] |
| 3 | API Key Encryption | P0 | [ ] |
| 4 | Password Hashing | P0 | [ ] |
| 5 | Connection Security (TLS) | P1 | [ ] |
| 6 | Connection Pooling | P2 | [ ] |
| 7 | Query Limits | P1 | [ ] |
| 8 | Migration Security | P2 | [ ] |
| 9 | Backup Security | P2 | [ ] |
| 10 | Database Logging | P2 | [ ] |

## References

- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine)
- [PostgreSQL Security](https://www.postgresql.org/docs/current/security.html)
- [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [OWASP Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
