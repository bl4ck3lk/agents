# Quick Security Scan Checklist

A rapid security assessment for the Agents LLM batch processing platform.

## Usage

```bash
./scripts/quick-scan.sh
```

Or run manually:

```bash
# Quick security audit - secrets, injection, dependencies
echo "=== Rapid Security Scan ===" && \
echo "\n--- Hardcoded Secrets ---" && \
grep -rE "(password|secret|api_key|token)\s*=\s*[\"'][^$\{]" agents/ 2>/dev/null && echo "WARN: Possible hardcoded secrets" || echo "OK: No obvious secrets" && \
echo "\n--- SQL Injection Vectors ---" && \
grep -rE "execute\(.*%|text\(.*\+|text\(.*format|\.raw\(" agents/db/ 2>/dev/null && echo "WARN: Possible SQL injection" || echo "OK: No obvious SQL injection" && \
echo "\n--- Command Injection ---" && \
grep -rE "subprocess|os\.system|shell=True|eval\(|exec\(" agents/ 2>/dev/null && echo "WARN: Possible command injection" || echo "OK: No obvious command injection" && \
echo "\n--- Dependency Audit ---" && \
uv pip list --outdated 2>/dev/null || pip list --outdated 2>/dev/null && echo "Check for outdated dependencies"
```

## Checklist

| # | Check | Command | Expected |
|---|-------|---------|----------|
| 1 | No hardcoded secrets | `grep -rE "(api_key|secret)\s*=\s*[\"'][^$\{]" agents/` | No matches |
| 2 | No SQL injection | `grep -rE "text\(.*\+|text\(.*format|\.raw\(" agents/db/` | No matches |
| 3 | No command injection | `grep -rE "subprocess|os\.system|shell=True|eval\(" agents/` | No matches |
| 4 | No debug mode in prod | `grep -rE "DEBUG.*=.*True|RELOAD.*true" docker-compose*.yml` | No matches |
| 5 | No default creds | `grep -rE "minioadmin|postgres:postgres|dev-secret-key" docker-compose*.yml` | Only in dev |
| 6 | Dependencies up to date | `uv pip list --outdated` | No outdated packages |
| 7 | API key encryption | `grep -r "APIKeyEncryption\|Fernet" agents/api/` | Found |
| 8 | Rate limiting | `grep -r "@limiter\.limit" agents/api/` | Found |
| 9 | Auth required | `grep -r "Depends\(current" agents/api/routes/` | Found |
| 10 | CORS restricted | `grep -r "allow_origins" agents/api/` | Not `*` |

## Priority Fixes

If any check fails, prioritize fixes:

**P0 (Critical)**
- Hardcoded secrets in code
- SQL injection vulnerabilities
- Command injection vulnerabilities
- Missing authentication on sensitive endpoints

**P1 (High)**
- Default credentials in production configs
- Missing rate limiting
- Debug mode enabled
- CORS set to `*` in production

**P2 (Medium)**
- Outdated dependencies with known CVEs
- Missing security headers
- Unrestricted presigned URLs

## Next Steps

If quick scan passes, proceed to full assessment in SKILL.md.
