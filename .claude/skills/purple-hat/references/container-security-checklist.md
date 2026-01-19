# Container Security Checklist

Security assessment for Docker containers in the Agents platform.

## Base Image Security

### Check Points

- [ ] Base image version pinned (not `:latest`)
- [ ] Using slim/alpine variant where possible
- [ ] Official images from trusted registry (Docker Hub, GHCR)
- [ ] Base image updated within last 90 days
- [ ] No unnecessary packages in base image

**Search Patterns:**
```bash
# Check base image specification
Grep: ^FROM
Path: Dockerfile

# Vulnerable patterns
Grep: FROM.*:latest|FROM.*:master|FROM.*:3
Path: Dockerfile
```

**Good vs Bad:**
```dockerfile
# BAD: Floating version, latest
FROM python:latest
FROM python:3

# GOOD: Version-pinned, slim
FROM python:3.12-slim
FROM python:3.12-bookworm-slim
```

---

## Non-Root User Execution

### Check Points

- [ ] Application runs as non-root user
- [ ] User created with explicit UID/GID
- [ ] No `USER root` after application setup
- [ ] WORKDIR owned by application user

**Search Patterns:**
```bash
# Check for USER directive
Grep: ^USER
Path: Dockerfile

# Check for user creation
Grep: useradd|adduser|groupadd|--uid|--gid|\d{4}
Path: Dockerfile
```

**Good Pattern:**
```dockerfile
# Create non-root user with explicit UID/GID
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home appuser

# Set as non-root user
USER appuser
WORKDIR /home/appuser/app
```

---

## Multi-Stage Build Security

### Check Points

- [ ] Multi-stage build used
- [ ] Build dependencies not in runtime image
- [ ] Intermediate layers cleaned up
- [ ] Secrets not present in any layer

**Search Patterns:**
```bash
# Check for multi-stage builds
Grep: ^FROM.*AS\s+\w+|COPY --from=
Path: Dockerfile

# Verify final stage doesn't have build tools
Grep: pip|npm|gcc|make|curl|wget|git
Path: Dockerfile  # Check if these are in final stage
```

**Good Pattern:**
```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Runtime stage (minimal)
FROM python:3.12-slim AS runtime
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --create-home appuser
WORKDIR /home/appuser/app
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=appuser:appgroup agents/ /home/appuser/app/agents
USER appuser
CMD ["agents-api"]
```

---

## File Permission Hardening

### Check Points

- [ ] No unnecessary SUID/SGID binaries
- [ ] Application files have minimal permissions
- [ ] Config files read-only
- [ ] tmpfs used for writable directories if needed

**Search Patterns:**
```bash
# Check for chmod/chown in Dockerfile
Grep: chmod|chown
Path: Dockerfile

# Check for read-only patterns
Grep: read_only.*true|readOnlyRootFilesystem
Path: docker-compose*.yml
```

**Good Pattern:**
```dockerfile
# Minimal permissions
RUN chmod 500 /app/entrypoint.sh && \
    chmod -R 400 /app/config/ && \
    chmod -R 500 /app/agents
```

---

## Docker Compose Security Contexts

### Check Points

- [ ] `no-new-privileges` enabled
- [ ] All capabilities dropped, only necessary ones added
- [ ] No privileged containers
- [ ] seccomp/AppArmor profiles applied (if available)
- [ ] Read-only root filesystem where possible
- [ ] Network segmentation between services

**Search Patterns:**
```bash
# Security context in docker-compose
Grep: security_opt|cap_drop|cap_add|no-new-privileges|privileged|read_only
Path: docker-compose*.yml

# Dangerous patterns
Grep: privileged.*true|--privileged
Path: docker-compose*.yml
```

**Good Configuration:**
```yaml
services:
  web-api:
    security_opt:
      - no-new-privileges:true
      - seccomp:unconfined  # Or custom profile path
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed for port < 1024
    read_only: true
    tmpfs:
      - /tmp:size=100M

  postgres:
    security_opt:
      - no-new-privileges:true
```

---

## Secrets in Docker

### Check Points

- [ ] No secrets in ARG or ENV instructions
- [ ] No .env files copied into image
- [ ] BuildKit secrets used for build-time credentials
- [ ] Secrets injected at runtime, not build time

**Search Patterns:**
```bash
# Secrets in build args (DANGEROUS)
Grep: ARG.*(SECRET|PASSWORD|KEY|TOKEN|API_KEY)
Path: Dockerfile

# COPY of sensitive files (DANGEROUS)
Grep: COPY.*(\.env|credentials|secrets|\.pem|\.key)
Path: Dockerfile

# BuildKit secrets usage (GOOD)
Grep: --mount=type=secret|RUN --mount
Path: Dockerfile
```

**Good Pattern (BuildKit Secrets):**
```dockerfile
# syntax=docker/dockerfile:1.4
RUN --mount=type=secret,id=npm_token \
    NPM_TOKEN=$(cat /run/secrets/npm_token) npm install
```

---

## Health Checks

### Check Points

- [ ] HEALTHCHECK directive configured
- [ ] Health check interval and timeout configured
- [ ] Health check tests application endpoint, not just process
- [ ] Health check doesn't expose sensitive data

**Search Patterns:**
```bash
# Check for HEALTHCHECK directive
Grep: HEALTHCHECK
Path: Dockerfile

# Check health check configuration
Grep: --interval|--timeout|--retries|--start-period
Path: Dockerfile
```

**Good Pattern:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1
```

---

## Container Registry Security

### Check Points

- [ ] Images stored in private registry
- [ ] Registry credentials via environment, not code
- [ ] Images tagged with immutable identifiers (SHA, not :latest)
- [ ] Image signing enabled (Cosign/Notary)

**Search Patterns:**
```bash
# Registry usage
Grep: docker\.io|ghcr\.io|registry|pull.*image
Path: docker-compose*.yml Makefile

# Tag patterns
Grep: :latest|:master|:dev|tag=
Path: Makefile docker-compose*.yml
```

---

## Image Scanning

### Check Points

- [ ] Images scanned for vulnerabilities (Trivy, Grype)
- [ ] No HIGH/CRITICAL CVEs in production images
- [ ] SBOM generated and validated
- [ ] Dockerfile linted (Hadolint)
- [ ] No secrets embedded in image layers

**Commands:**
```bash
# Primary scan - Trivy
trivy image --severity HIGH,CRITICAL agents:latest

# Secondary scan - Grype
grype agents:latest --fail-on high

# SBOM-based scanning
syft agents:latest -o cyclonedx-json > sbom.json
grype sbom:sbom.json

# Secret scanning
trivy image --scanners secret agents:latest

# Dockerfile linting
hadolint Dockerfile
dockle agents:latest
```

---

## Runtime Security

### Check Points

- [ ] Container runtime uses security profiles
- [ ] Resource limits configured (CPU, memory)
- [ ] Network segmentation (services isolated)
- [ ] Container restart policy configured
- [ ] Logs collected and monitored

**Configuration:**
```yaml
services:
  web-api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
    restart_policy: on-failure
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## Quick Container Security Scan

```bash
# Run all container security checks
echo "=== Container Security Scan ===" && \
echo "\n--- Base Image ---" && \
grep "^FROM" Dockerfile && echo "Review base image" && \
echo "\n--- Non-Root User ---" && \
grep "^USER" Dockerfile && echo "OK" || echo "WARN: No USER directive" && \
echo "\n--- Multi-Stage Build ---" && \
grep "COPY --from=" Dockerfile && echo "OK" || echo "WARN: Consider multi-stage build" && \
echo "\n--- Privileged Mode ---" && \
grep "privileged.*true" docker-compose*.yml && echo "WARN: Privileged container" || echo "OK" && \
echo "\n--- Secrets in Docker ---" && \
grep "ARG.*SECRET\|COPY.*\.env" Dockerfile && echo "WARN: Secrets in Dockerfile" || echo "OK"
```

## Priority Summary

| # | Area | Priority | Status |
|---|-------|----------|--------|
| 1 | Non-Root User | P0 | [ ] |
| 2 | No Privileged Containers | P0 | [ ] |
| 3 | Base Image Pinned | P1 | [ ] |
| 4 | No Secrets in Image | P0 | [ ] |
| 5 | Multi-Stage Build | P1 | [ ] |
| 6 | Resource Limits | P1 | [ ] |
| 7 | Health Checks | P2 | [ ] |
| 8 | Image Scanning | P1 | [ ] |
| 9 | File Permissions | P2 | [ ] |
| 10 | Network Segmentation | P2 | [ ] |

## References

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [OCI Image Format Specification](https://github.com/opencontainers/image-spec)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Hadolint Rules](https://github.com/hadolint/hadolint)
