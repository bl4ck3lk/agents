# Security Scripts

Automated security scanning and assessment scripts for the Agents platform.

## Available Scripts

| Script | Description | Usage |
|---------|-------------|--------|
| `quick-scan.sh` | Rapid security audit (secrets, injection, dependencies) | `./quick-scan.sh` |
| `llm-security-scan.sh` | LLM-specific security checks | `./llm-security-scan.sh` |
| `secrets-scan.sh` | Scan for hardcoded secrets | `./secrets-scan.sh [--json]` |
| `dependency-audit.sh` | Check dependencies for vulnerabilities | `./dependency-audit.sh` |
| `container-scan.sh` | Docker container security scan | `./container-scan.sh` |
| `ci-cd-scan.sh` | GitHub Actions security scan | `./ci-cd-scan.sh` |

## Running All Scans

```bash
# Run all security checks
./quick-scan.sh && \
./llm-security-scan.sh && \
./secrets-scan.sh && \
./dependency-audit.sh && \
./container-scan.sh && \
./ci-cd-scan.sh
```

## Prerequisites

```bash
# Install required tools
pip install pip-audit safety
pip install trivy  # for container scanning
```

## Output

Scripts output to both console and can generate JSON reports:

```bash
./secrets-scan.sh --json > security-report.json
```

## CI/CD Integration

Add to `.github/workflows/security.yml`:

```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Security Scan
        run: |
          cd .claude/skills/purple-hat/scripts
          ./quick-scan.sh
          ./llm-security-scan.sh
          ./secrets-scan.sh
          ./dependency-audit.sh
```

## References

- See main SKILL.md for detailed methodology
- See reference checklists for specific areas
