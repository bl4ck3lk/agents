# Purple Hat Security Assessment Framework

## Overview
Comprehensive security pentesting framework for the Agents LLM batch processing platform. Combines offensive (red team) discovery with defensive (blue team) remediation guidance.

## Quick Links

### Core Documentation
- [Main Methodology](SKILL.md)
- [Quick Reference](QUICK-REF.md)
- [Test Payloads](references/test-payloads.md)

### Security Checklists
- [LLM Security](references/llm-security-checklist.md)
- [FastAPI Security](references/fastapi-security-checklist.md)
- [S3/MinIO Security](references/s3-security-checklist.md)
- [API Security](references/api-security-checklist.md)
- [Container Security](references/container-security-checklist.md)
- [File Upload Security](references/file-upload-security-checklist.md)
- [Auth Security](references/auth-security-checklist.md)
- [Database Security](references/database-security-checklist.md)

### Operational Security
- [Incident Response](references/incident-response.md)
- [Secrets Management](references/secrets-management.md)
- [Security Review Checklist](references/security-review-checklist.md)
- [CI/CD Security Workflow](references/ci-security-workflow.md)
- [Supply Chain Security](references/supply-chain-security.md)

## Automation
- [Scripts](scripts/README.md)
- [Quick Scan Script](scripts/quick-scan.sh)
- [LLM Security Scan](scripts/llm-security-scan.sh)
- [Secrets Scan](scripts/secrets-scan.sh)
- [Dependency Audit](scripts/dependency-audit.sh)
- [Container Scan](scripts/container-scan.sh)

## Security Standards Covered
- OWASP Top 10 2021
- OWASP API Security Top 10 2023
- OWASP LLM Top 10 2025
- FastAPI Security Best Practices
- SQLAlchemy Security
- NIST Cybersecurity Framework
- PCI-DSS (for payment processing if applicable)
- MITRE ATT&CK

## Usage
```bash
# Quick security scan
./scripts/quick-scan.sh

# LLM-specific security scan
./scripts/llm-security-scan.sh

# Secrets scan
./scripts/secrets-scan.sh --json

# Full dependency audit
./scripts/dependency-audit.sh

# Container security scan
./scripts/container-scan.sh

# Generate security report
./scripts/generate-report.sh --json --output report.json
```

## Version History
See [CHANGELOG](SKILL.md#changelog) in SKILL.md

## License
See repository license
