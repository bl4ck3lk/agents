# Incident Response Guide

Practical incident response for solo developers and small teams.

---

## Severity Classification

### Critical (P0) - Act Immediately
**Response Time: < 1 hour**

Examples:
- Active data breach or exfiltration
- Production database exposed/compromised
- API keys or secrets leaked publicly (GitHub, logs)
- Authentication bypass in production
- Active exploitation detected

Actions:
1. **Contain** - Take affected systems offline if safe
2. **Rotate** - Immediately rotate all exposed secrets
3. **Notify** - Users if their data was affected (legal requirement)
4. **Document** - Screenshot/log everything before fixing

### High (P1) - Act Today
**Response Time: < 24 hours**

Examples:
- SQL injection vulnerability discovered
- Privilege escalation possible
- IDOR allowing access to other users' data
- Hardcoded secrets in codebase
- Outdated dependency with known exploit

Actions:
1. **Assess** - Determine if already exploited
2. **Patch** - Deploy fix to production
3. **Review** - Check logs for exploitation attempts
4. **Prevent** - Add tests to prevent regression

### Medium (P2) - Act This Week
**Response Time: < 7 days**

Examples:
- Missing rate limiting on sensitive endpoints
- Weak password policy
- Security headers not configured
- Debug mode enabled in staging
- Outdated dependencies (no known exploits)

Actions:
1. **Schedule** - Add to sprint/backlog
2. **Mitigate** - Add compensating controls if possible
3. **Fix** - Deploy within the week

### Low (P3) - Act This Month
**Response Time: < 30 days**

Examples:
- Minor information disclosure (version numbers)
- Best practice deviations
- Documentation gaps
- Non-critical security improvements

Actions:
1. **Document** - Create issue/ticket
2. **Prioritize** - Schedule alongside other work

---

## Incident Response Checklist

### Immediate (First 15 Minutes)

```markdown
## Incident: [Brief Description]
**Detected:** [Date/Time]
**Severity:** P0/P1/P2/P3
**Status:** Active / Contained / Resolved

### Initial Assessment
- [ ] What happened? (brief description)
- [ ] What systems are affected?
- [ ] Is it ongoing or past?
- [ ] How was it detected?

### Containment (if P0/P1)
- [ ] Take affected system offline (if safe)
- [ ] Revoke compromised credentials
- [ ] Block suspicious IPs (if applicable)
- [ ] Preserve evidence (logs, screenshots)
```

### Investigation (First Hour)

```markdown
### Investigation
- [ ] Review logs for suspicious activity
- [ ] Identify attack vector/root cause
- [ ] Determine scope of impact
- [ ] Check if data was accessed/exfiltrated

### Evidence Collection
- [ ] Export relevant logs
- [ ] Screenshot error messages
- [ ] Document timeline of events
- [ ] Save any artifacts (malicious payloads, etc.)
```

### Resolution

```markdown
### Resolution
- [ ] Develop and test fix
- [ ] Deploy fix to production
- [ ] Verify fix is effective
- [ ] Rotate any exposed secrets
- [ ] Update dependencies if relevant

### Communication (if user data affected)
- [ ] Draft user notification
- [ ] Notify affected users
- [ ] Update status page (if applicable)
```

### Post-Incident

```markdown
### Post-Incident Review
- [ ] What went wrong?
- [ ] How can we prevent this?
- [ ] What monitoring would have caught this earlier?
- [ ] Add regression test
- [ ] Update security checklist
```

---

## Common Scenarios

### Scenario: Secret Leaked to GitHub

**Detection:** GitHub secret scanning alert, or manual discovery

**Immediate Actions:**
```bash
# 1. Rotate the secret immediately
# If OPENAI_API_KEY leaked:
# - Go to OpenAI dashboard
# - Revoke the old key
# - Generate new key
# - Update production environment

# 2. Update local/CI environments
# Update .env files
# Update GitHub Secrets
# Update deployment platform (Railway, Fly, etc.)

# 3. Check for unauthorized usage
# Review OpenAI usage dashboard
# Check billing for unexpected charges
```

**Prevention:**
- Add pre-commit hook for secret scanning
- Use `.env` files (never commit)
- Use GitHub's secret scanning

### Scenario: SQL Injection Found

**Detection:** Security scan, code review, or penetration test

**Immediate Actions:**
```bash
# 1. Assess exploitation
# Check logs for injection attempts
grep -E "UNION|SELECT.*FROM|DROP|;--" /var/log/app/*.log

# 2. Determine scope
# Which endpoints are affected?
# What data could be accessed?

# 3. Deploy fix
# Convert raw SQL to parameterized queries
# Add input validation
# Deploy to production
```

**Prevention:**
- Always use SQLAlchemy ORM
- Add Pydantic validation on all inputs
- Add security scanning to CI

### Scenario: User Reports Seeing Another User's Data

**Detection:** User report

**Immediate Actions:**
```markdown
1. **Verify** - Reproduce the issue
2. **Contain** - Disable affected endpoint if critical
3. **Assess** - How many users affected?
4. **Fix** - Add proper ownership filtering
5. **Notify** - Affected users if data was exposed
```

**Code Fix Pattern:**
```python
# BEFORE (vulnerable)
@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    return await job_repo.get(job_id)

# AFTER (secure)
@router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: User = Depends(get_current_user)):
    job = await job_repo.get(job_id)
    if job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    return job
```

### Scenario: Prompt Injection Successful

**Detection:** User reports unexpected LLM output, logs show suspicious prompts

**Immediate Actions:**
```markdown
1. **Review** - What data was potentially leaked?
2. **Assess** - Can the LLM access sensitive data?
3. **Contain** - Add input sanitization
4. **Fix** - Implement proper prompt construction
```

**Prevention:**
```python
# Validate/sanitize user input before prompt construction
def sanitize_prompt_input(user_input: str) -> str:
    # Remove potential injection markers
    sanitized = user_input.replace("```", "")
    sanitized = sanitized.replace("SYSTEM:", "")
    sanitized = sanitized.replace("INSTRUCTIONS:", "")
    # Truncate to reasonable length
    return sanitized[:500]
```

---

## Log Analysis Commands

### Search for Suspicious Activity

```bash
# Failed authentication attempts
grep -E "401|403|Unauthorized|authentication failed" /var/log/app/*.log

# SQL injection attempts
grep -E "UNION|SELECT.*FROM|DROP|INSERT.*INTO|;--" /var/log/app/*.log

# Path traversal attempts
grep -E "\.\./|%2e%2e|%252e" /var/log/app/*.log

# Unusual API activity
grep -E "429|rate.limit|too.many.requests" /var/log/app/*.log

# Error spikes (potential attack)
grep -E "500|error|exception" /var/log/app/*.log | wc -l
```

### Export Logs for Analysis

```bash
# Export last 24 hours
journalctl --since "24 hours ago" > incident_logs.txt

# Export specific time range
journalctl --since "2025-01-18 10:00:00" --until "2025-01-18 12:00:00" > incident_logs.txt

# Docker logs
docker logs --since 24h app_container > incident_logs.txt
```

---

## Secret Rotation Checklist

When secrets are compromised, rotate in this order:

```markdown
### Priority 1: External API Keys
- [ ] OPENAI_API_KEY - OpenAI dashboard
- [ ] Database credentials - Cloud provider console
- [ ] AWS/GCP credentials - IAM console

### Priority 2: Application Secrets
- [ ] SECRET_KEY (JWT signing) - Regenerate, redeploy
- [ ] ENCRYPTION_KEY - Regenerate, re-encrypt stored data
- [ ] Database password - Update in all environments

### Priority 3: Service Credentials
- [ ] MinIO/S3 credentials - MinIO console
- [ ] SMTP credentials - Email provider

### After Rotation
- [ ] Update .env.example (if structure changed)
- [ ] Update CI/CD secrets
- [ ] Update production environment
- [ ] Verify application still works
- [ ] Document new secret storage location
```

---

## Communication Templates

### User Notification (Data Breach)

```
Subject: Security Notice - [Your App Name]

Dear [User],

We are writing to inform you of a security incident that may have affected your account.

What happened:
[Brief, honest description of what occurred]

What information was involved:
[Specific data types - email, job history, etc.]

What we're doing:
[Steps you've taken to address the issue]

What you can do:
- Change your password at [link]
- Review your account activity
- Contact us at [email] with questions

We take your security seriously and apologize for any concern this may cause.

Sincerely,
[Your name]
```

### Status Page Update

```
[Date/Time] - Investigating
We are investigating reports of [issue description].

[Date/Time] - Identified
We have identified the cause and are implementing a fix.

[Date/Time] - Resolved
The issue has been resolved. [Brief explanation of what happened and what was done].
```

---

## Post-Incident Review Template

```markdown
# Post-Incident Review

**Incident:** [Title]
**Date:** [Date]
**Severity:** P0/P1/P2/P3
**Duration:** [Time from detection to resolution]

## Summary
[2-3 sentence description of what happened]

## Timeline
- [Time] - [Event]
- [Time] - [Event]
- [Time] - [Event]

## Root Cause
[What was the underlying cause?]

## Impact
- Users affected: [Number]
- Data exposed: [Yes/No, what type]
- Downtime: [Duration]

## What Went Well
- [Positive aspect]
- [Positive aspect]

## What Could Be Improved
- [Improvement area]
- [Improvement area]

## Action Items
- [ ] [Specific action] - [Owner] - [Due date]
- [ ] [Specific action] - [Owner] - [Due date]

## Prevention Measures
- [What will prevent this from happening again?]
```

---

## Quick Reference

| Severity | Response Time | Example | Action |
|----------|--------------|---------|--------|
| P0 Critical | < 1 hour | Data breach, secrets leaked | Stop everything, fix now |
| P1 High | < 24 hours | SQLi, auth bypass | Fix today |
| P2 Medium | < 7 days | Missing rate limit | Fix this week |
| P3 Low | < 30 days | Best practice gaps | Schedule fix |

---

## Tools

### Local Analysis
```bash
# grep for log analysis
# jq for JSON parsing
# sqlite3 for checkpoint analysis
```

### Online Resources
- [Have I Been Pwned](https://haveibeenpwned.com/) - Check for credential leaks
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)
- [VirusTotal](https://www.virustotal.com/) - Check suspicious files/URLs

---

## References

- [NIST Incident Response](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r2.pdf)
- [OWASP Incident Response](https://owasp.org/www-project-incident-response/)
