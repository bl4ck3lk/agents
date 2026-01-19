# Secrets Management Guide

Practical secrets management for solo developers and small teams.

---

## Principles

1. **Never commit secrets** to version control
2. **Use environment variables** for all secrets
3. **Rotate secrets** regularly and after any incident
4. **Limit access** - only grant what's needed
5. **Audit usage** - know when secrets are used

---

## Secret Types in This Project

| Secret | Purpose | Rotation Frequency |
|--------|---------|-------------------|
| `OPENAI_API_KEY` | LLM API access | On compromise, or yearly |
| `SECRET_KEY` | JWT signing | On compromise, or yearly |
| `ENCRYPTION_KEY` | API key encryption at rest | On compromise |
| `DATABASE_URL` | PostgreSQL connection | On compromise |
| `MINIO_ROOT_USER` | S3/MinIO admin | On compromise |
| `MINIO_ROOT_PASSWORD` | S3/MinIO admin | On compromise |

---

## Local Development

### .env File Setup

```bash
# Create from template
cp .env.example .env

# Edit with your values
nano .env
```

### .env.example (commit this)
```bash
# API Keys
OPENAI_API_KEY=sk-...your-key-here...
OPENAI_BASE_URL=https://api.openai.com/v1

# Security
SECRET_KEY=generate-a-32-char-random-string
ENCRYPTION_KEY=generate-a-32-byte-fernet-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/agents

# Storage (MinIO)
MINIO_ROOT_USER=your-minio-user
MINIO_ROOT_PASSWORD=your-minio-password
S3_ENDPOINT_URL=http://localhost:9000
```

### Generate Secure Values

```python
# Generate SECRET_KEY (32+ characters)
import secrets
print(secrets.token_urlsafe(32))

# Generate ENCRYPTION_KEY (Fernet)
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())

# Generate secure password
import secrets
print(secrets.token_urlsafe(24))
```

```bash
# Or via command line
openssl rand -base64 32  # For SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### .gitignore (required entries)

```gitignore
# Environment files
.env
.env.local
.env.*.local

# Never commit these
*.pem
*.key
credentials.json
secrets.json
```

---

## Production Deployment

### Option 1: Platform Environment Variables (Recommended for Solo Dev)

Most deployment platforms support environment variables:

**Railway:**
```bash
railway variables set OPENAI_API_KEY=sk-xxx
railway variables set SECRET_KEY=xxx
```

**Fly.io:**
```bash
fly secrets set OPENAI_API_KEY=sk-xxx
fly secrets set SECRET_KEY=xxx
```

**Render:**
- Dashboard → Environment → Add Environment Variable

**Heroku:**
```bash
heroku config:set OPENAI_API_KEY=sk-xxx
heroku config:set SECRET_KEY=xxx
```

### Option 2: Docker Compose (Self-Hosted)

```yaml
# docker-compose.prod.yml
services:
  api:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SECRET_KEY=${SECRET_KEY}
      - DATABASE_URL=${DATABASE_URL}
    env_file:
      - .env.prod  # Not committed to git
```

### Option 3: GitHub Actions Secrets

For CI/CD pipelines:

1. Go to Repository → Settings → Secrets and variables → Actions
2. Add each secret:
   - `OPENAI_API_KEY`
   - `SECRET_KEY`
   - etc.

Use in workflows:
```yaml
env:
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  SECRET_KEY: ${{ secrets.SECRET_KEY }}
```

---

## Secret Rotation

### When to Rotate

- **Immediately:** After any suspected compromise
- **Immediately:** After team member leaves
- **Immediately:** After secret appears in logs/error messages
- **Annually:** As a precaution (set calendar reminder)

### Rotation Procedure

#### OPENAI_API_KEY
```markdown
1. Go to https://platform.openai.com/api-keys
2. Create new key
3. Update in all environments (local, CI, production)
4. Verify application works
5. Revoke old key
```

#### SECRET_KEY (JWT Signing)
```markdown
1. Generate new key: `openssl rand -base64 32`
2. Update in production environment
3. Deploy new version
4. Note: All existing JWTs will be invalidated (users must re-login)
```

#### ENCRYPTION_KEY (API Keys at Rest)
```markdown
⚠️ CAUTION: Changing this will make existing encrypted data unreadable

1. Generate new key
2. Write migration to re-encrypt all API keys:
   a. Decrypt with old key
   b. Re-encrypt with new key
3. Deploy migration
4. Update environment with new key
5. Securely delete old key
```

#### DATABASE_URL
```markdown
1. Create new database user with same permissions
2. Update connection string in all environments
3. Deploy and verify
4. Remove old database user
```

---

## Pre-Commit Secret Scanning

### Setup detect-secrets

```bash
# Install
pip install detect-secrets

# Initialize baseline (in project root)
detect-secrets scan > .secrets.baseline

# Add pre-commit hook
```

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

### Install hooks

```bash
pip install pre-commit
pre-commit install
```

Now secrets will be blocked from commits.

---

## Security Checklist

### Development Environment

- [ ] `.env` file exists and is in `.gitignore`
- [ ] `.env.example` has placeholder values (not real secrets)
- [ ] No secrets in code comments
- [ ] No secrets in error messages or logs
- [ ] Pre-commit hook blocks secrets

### Production Environment

- [ ] Secrets stored in platform's secret manager
- [ ] Secrets not in docker-compose files (use env_file)
- [ ] Secrets not in Dockerfiles
- [ ] Secrets not in CI/CD workflow files (use GitHub Secrets)
- [ ] Production uses different secrets than development

### Access Control

- [ ] Only necessary people have access to secrets
- [ ] API keys have minimal required permissions
- [ ] Database user has minimal required permissions

---

## Common Mistakes to Avoid

### 1. Hardcoded Secrets
```python
# BAD
OPENAI_API_KEY = "sk-abc123..."

# GOOD
import os
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
```

### 2. Secrets in Logs
```python
# BAD
logger.info(f"Using API key: {api_key}")
logger.error(f"Failed with config: {config}")  # config might contain secrets

# GOOD
logger.info("Using API key: [REDACTED]")
logger.error(f"Failed with config: {config.redacted()}")
```

### 3. Secrets in Error Messages
```python
# BAD
raise ValueError(f"Invalid key: {api_key}")

# GOOD
raise ValueError("Invalid API key provided")
```

### 4. Secrets in Git History
```bash
# If you accidentally committed a secret:
# 1. Rotate the secret IMMEDIATELY (assume compromised)
# 2. Remove from history (optional, secret is already compromised)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/secret/file' \
  --prune-empty --tag-name-filter cat -- --all
```

### 5. Same Secrets Across Environments
```markdown
# BAD: Same SECRET_KEY in dev and prod

# GOOD: Different secrets per environment
- Development: SECRET_KEY=dev-xxx
- Staging: SECRET_KEY=staging-xxx
- Production: SECRET_KEY=prod-xxx
```

---

## Quick Commands

```bash
# Check for secrets in codebase
grep -rE "(api_key|secret|password|token)\s*=\s*[\"'][^$\{]" agents/

# Scan with detect-secrets
detect-secrets scan --all-files

# Generate secure values
openssl rand -base64 32
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Check environment variables are set
env | grep -E "OPENAI|SECRET|DATABASE|MINIO"
```

---

## Emergency: Secret Leaked

If a secret is exposed (GitHub, logs, error messages):

```markdown
## Immediate Actions (< 15 minutes)

1. [ ] Rotate the secret at the source (API dashboard, etc.)
2. [ ] Update all environments with new secret
3. [ ] Deploy to production
4. [ ] Verify application works

## Investigation (< 1 hour)

5. [ ] Check for unauthorized usage (API dashboards, billing)
6. [ ] Review logs for suspicious activity
7. [ ] Determine how the leak occurred

## Prevention (< 1 day)

8. [ ] Add pre-commit hook if not present
9. [ ] Add secret to .gitignore patterns
10. [ ] Document in post-incident review
```

---

## References

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [12 Factor App - Config](https://12factor.net/config)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [detect-secrets](https://github.com/Yelp/detect-secrets)
