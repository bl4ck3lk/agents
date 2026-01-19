# Supply Chain Security

Protecting against vulnerabilities in dependencies and third-party code.

---

## Why This Matters

Your application inherits the security posture of every dependency. A vulnerable or malicious package can:
- Expose your users' data
- Give attackers access to your systems
- Compromise API keys and secrets

---

## Dependency Management

### Pin Versions in pyproject.toml

```toml
# BAD - Unpinned (gets latest, may break or be vulnerable)
[project]
dependencies = [
    "fastapi",
    "openai",
]

# BETTER - Minimum version
[project]
dependencies = [
    "fastapi>=0.109.0",
    "openai>=1.0.0",
]

# BEST - Exact version (fully reproducible)
[project]
dependencies = [
    "fastapi==0.109.2",
    "openai==1.12.0",
]
```

### Use Lock Files

```bash
# Generate lock file with uv
uv pip compile pyproject.toml -o requirements.lock

# Or with pip-tools
pip-compile pyproject.toml -o requirements.lock

# Install from lock file
uv pip install -r requirements.lock
```

---

## Vulnerability Scanning

### Regular Scanning

```bash
# pip-audit - check for known vulnerabilities
pip-audit

# With specific output
pip-audit --format json --output audit.json
pip-audit --desc on  # Show descriptions

# Safety (alternative)
safety check
safety check --full-report
```

### Automated Scanning (CI)

See `ci-security-workflow.md` for GitHub Actions integration.

### Interpreting Results

```
Found 2 known vulnerabilities in 1 package

Name     Version ID             Fix Versions
-------- ------- -------------- ------------
requests 2.25.1  PYSEC-2023-XXX >=2.31.0

HIGH: CVE-2023-XXXX - HTTP request smuggling vulnerability
```

**Action:**
1. Check if vulnerability affects your usage
2. Update to fixed version
3. If no fix available, consider alternatives or mitigations

---

## Dependency Review

### Before Adding a Dependency

Ask these questions:

1. **Is it necessary?** Can you implement the functionality yourself (if simple)?
2. **Is it maintained?** Check last commit date, open issues, maintainer activity
3. **Is it popular/trusted?** Check downloads, stars, known users
4. **Is it secure?** Check for past vulnerabilities, security policies
5. **What's the license?** Ensure compatibility with your project

### Quick Check Commands

```bash
# Check package info
pip show <package>
pip show --verbose <package>

# Check on PyPI
# Visit https://pypi.org/project/<package>/

# Check vulnerabilities
pip-audit -r requirements.txt | grep <package>
```

### Red Flags

- No updates in > 1 year
- Maintainer not responding to issues
- Multiple unpatched vulnerabilities
- Suspicious code in source
- Typosquatting (package name similar to popular one)

---

## LLM SDK Security

### OpenAI SDK

```bash
# Check current version
pip show openai

# Check for updates
pip index versions openai

# Update to latest
pip install --upgrade openai
```

**Security considerations:**
- Keep SDK updated (security patches)
- Pin to specific version in production
- Review changelog for security fixes

### Anthropic SDK

```bash
# Check current version
pip show anthropic

# Update
pip install --upgrade anthropic
```

---

## Dependabot Configuration

Enable automatic dependency updates:

`.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
```

### Handling Dependabot PRs

1. **Security updates (High/Critical)**: Merge promptly after CI passes
2. **Minor updates**: Review changelog, merge if no breaking changes
3. **Major updates**: Test thoroughly, may require code changes

---

## Software Bill of Materials (SBOM)

Generate a list of all dependencies for auditing:

```bash
# Generate requirements list
pip freeze > requirements.txt

# Or with more detail (CycloneDX format)
pip install cyclonedx-bom
cyclonedx-py environment > sbom.json

# Or with pip-licenses (includes license info)
pip install pip-licenses
pip-licenses --format=json > licenses.json
pip-licenses --format=markdown > LICENSES.md
```

---

## Container Base Image Security

### Pin Base Image

```dockerfile
# BAD - Floating tag
FROM python:3.12

# BETTER - Specific version
FROM python:3.12.1-slim

# BEST - SHA digest (immutable)
FROM python:3.12.1-slim@sha256:abc123...
```

### Scan Container Images

```bash
# Trivy - comprehensive scanner
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image your-image:latest

# Quick scan for HIGH and CRITICAL only
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image --severity HIGH,CRITICAL your-image:latest
```

---

## GitHub Actions Security

### Pin Actions to SHA

```yaml
# BAD - Tag can be changed
- uses: actions/checkout@v4

# GOOD - Pinned to SHA (immutable)
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4.1.1
```

### Find SHA for Actions

```bash
# Get SHA for a tag
git ls-remote --tags https://github.com/actions/checkout | grep v4.1.1
```

Or use GitHub's Dependabot to update actions automatically.

---

## Quick Security Checklist

### Weekly

- [ ] Run `pip-audit` and review results
- [ ] Check Dependabot alerts in GitHub
- [ ] Review and merge dependency update PRs

### Monthly

- [ ] Review unused dependencies, remove if not needed
- [ ] Check for major version updates
- [ ] Regenerate lock file

### Quarterly

- [ ] Full dependency audit
- [ ] Review container base images
- [ ] Update GitHub Actions to latest SHA

---

## Emergency: Vulnerable Dependency

When a critical vulnerability is announced:

```markdown
## Immediate Actions

1. [ ] Check if your version is affected
   pip show <package>

2. [ ] Check if vulnerability impacts your usage
   - Read the CVE description
   - Determine if affected code path is used

3. [ ] Update if affected
   pip install --upgrade <package>
   # Update lock file
   uv pip compile pyproject.toml -o requirements.lock

4. [ ] Deploy to production

5. [ ] Check for exploitation
   - Review logs for suspicious activity
   - Check if data was accessed
```

---

## Useful Tools

| Tool | Purpose | Command |
|------|---------|---------|
| pip-audit | Vulnerability scanning | `pip-audit` |
| safety | Vulnerability scanning | `safety check` |
| pip-licenses | License compliance | `pip-licenses` |
| cyclonedx-bom | SBOM generation | `cyclonedx-py environment` |
| Trivy | Container scanning | `trivy image <image>` |
| Dependabot | Auto-update dependencies | GitHub config |

---

## References

- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [pip-audit Documentation](https://github.com/pypa/pip-audit)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [SLSA Framework](https://slsa.dev/)
- [CycloneDX](https://cyclonedx.org/)
