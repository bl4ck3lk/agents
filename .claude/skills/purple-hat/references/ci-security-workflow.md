# CI/CD Security Workflow

GitHub Actions workflow for automated security scanning.

---

## Quick Setup

1. Copy the workflow file to `.github/workflows/security.yml`
2. Enable Dependabot in repository settings
3. Configure branch protection rules

---

## Security Workflow

Create `.github/workflows/security.yml`:

```yaml
name: Security Scan

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    # Run weekly on Monday at 9 AM UTC
    - cron: '0 9 * * 1'
  workflow_dispatch:  # Allow manual trigger

jobs:
  security-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write  # For CodeQL

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install --system -e ".[dev]"
          pip install pip-audit bandit safety

      # Static Analysis
      - name: Run Bandit (Python Security Linter)
        run: |
          bandit -r agents/ -f json -o bandit-report.json || true
          bandit -r agents/ -ll  # Print high/medium issues
        continue-on-error: true

      - name: Upload Bandit Report
        uses: actions/upload-artifact@v4
        with:
          name: bandit-report
          path: bandit-report.json
        if: always()

      # Dependency Scanning
      - name: Run pip-audit
        run: |
          pip-audit --desc on --format json --output pip-audit-report.json || true
          pip-audit --desc on  # Print to console
        continue-on-error: true

      - name: Upload pip-audit Report
        uses: actions/upload-artifact@v4
        with:
          name: pip-audit-report
          path: pip-audit-report.json
        if: always()

      # Secret Scanning
      - name: Check for hardcoded secrets
        run: |
          echo "=== Checking for hardcoded secrets ==="
          if grep -rE "(password|secret|api_key|token)\s*=\s*[\"'][^$\{]" agents/ --include="*.py"; then
            echo "::warning::Possible hardcoded secrets found"
          else
            echo "No hardcoded secrets detected"
          fi

      # SQL Injection Check
      - name: Check for SQL injection vectors
        run: |
          echo "=== Checking for SQL injection vectors ==="
          if grep -rE "execute\(.*%|text\(.*\+|text\(.*format|\.raw\(" agents/ --include="*.py"; then
            echo "::error::Possible SQL injection vectors found"
            exit 1
          else
            echo "No SQL injection vectors detected"
          fi

      # Command Injection Check
      - name: Check for command injection vectors
        run: |
          echo "=== Checking for command injection vectors ==="
          FOUND=$(grep -rE "subprocess\..*shell=True|os\.system\(" agents/ --include="*.py" || true)
          if [ -n "$FOUND" ]; then
            echo "::warning::Possible command injection vectors found"
            echo "$FOUND"
          else
            echo "No command injection vectors detected"
          fi

      # Type Checking (catches some security issues)
      - name: Run mypy
        run: mypy agents/ --ignore-missing-imports
        continue-on-error: true

      # Run quick scan script if it exists
      - name: Run Quick Security Scan
        run: |
          if [ -f ".claude/skills/purple-hat/scripts/quick-scan.sh" ]; then
            chmod +x .claude/skills/purple-hat/scripts/quick-scan.sh
            .claude/skills/purple-hat/scripts/quick-scan.sh || true
          fi
        continue-on-error: true

  # Dependency Review (for PRs)
  dependency-review:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Dependency Review
        uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: high

  # CodeQL Analysis (optional, more comprehensive)
  codeql:
    runs-on: ubuntu-latest
    if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository
    permissions:
      security-events: write
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: python

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
```

---

## Dependabot Configuration

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "deps"
    # Group minor/patch updates
    groups:
      minor-and-patch:
        patterns:
          - "*"
        update-types:
          - "minor"
          - "patch"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "ci"
    commit-message:
      prefix: "ci"
```

---

## Branch Protection Rules

In repository Settings → Branches → Add rule:

```
Branch name pattern: main

Protect matching branches:
☑ Require a pull request before merging
  ☑ Require approvals: 1 (or 0 for solo dev)
  ☑ Dismiss stale pull request approvals when new commits are pushed

☑ Require status checks to pass before merging
  ☑ Require branches to be up to date before merging
  Status checks:
    - security-scan
    - dependency-review (if enabled)

☑ Do not allow bypassing the above settings
```

---

## Secret Scanning Setup

GitHub provides free secret scanning. Enable it:

1. Repository Settings → Code security and analysis
2. Enable:
   - ☑ Dependency graph
   - ☑ Dependabot alerts
   - ☑ Dependabot security updates
   - ☑ Secret scanning
   - ☑ Push protection (blocks commits with secrets)

---

## Pre-commit Hooks (Local)

For local development, add `.pre-commit-config.yaml`:

```yaml
repos:
  # Secrets detection
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']

  # Python linting (catches some security issues)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  # Security linting
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.6
    hooks:
      - id: bandit
        args: ["-ll", "-r", "agents/"]

  # Check for large files (potential data leaks)
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: detect-private-key
```

Install:
```bash
pip install pre-commit
pre-commit install
```

---

## Scheduled Security Audit

The workflow runs weekly, but for a manual audit:

```bash
# Run all security checks locally
pip-audit
bandit -r agents/ -ll
safety check
./scripts/quick-scan.sh
```

---

## Handling Security Alerts

When Dependabot or security scan finds issues:

### High/Critical Vulnerability
1. Check if the vulnerability affects your usage
2. Update the dependency immediately if affected
3. If update breaks things, find alternative or mitigation

### Medium/Low Vulnerability
1. Add to backlog
2. Update when convenient
3. Group with other dependency updates

### Secret Detected
1. **Immediately** rotate the secret
2. Fix the code
3. Check git history for exposure
4. See incident response guide

---

## Security Badge

Add to README.md:

```markdown
![Security Scan](https://github.com/YOUR_USERNAME/agents/actions/workflows/security.yml/badge.svg)
```

---

## Quick Reference

| Tool | Purpose | When Run |
|------|---------|----------|
| Bandit | Python security linting | Every push/PR |
| pip-audit | Dependency vulnerabilities | Every push/PR |
| Dependabot | Dependency updates | Weekly |
| CodeQL | Deep code analysis | Every push |
| Secret scanning | Detect leaked secrets | Every push |
| Pre-commit | Local secret/lint checks | Before commit |

---

## References

- [GitHub Actions Security Hardening](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [CodeQL Documentation](https://docs.github.com/en/code-security/code-scanning/automatically-scanning-your-code-for-vulnerabilities-and-errors/about-code-scanning-with-codeql)
