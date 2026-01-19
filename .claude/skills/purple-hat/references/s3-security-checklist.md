# S3/MinIO Security Checklist

Security assessment for S3-compatible storage (MinIO) in the Agents platform.

## Overview

This checklist covers S3/MinIO security including presigned URLs, bucket policies, and object access controls.

## Presigned URL Security

### Check Points

- [ ] Presigned URL expiry time configured (not infinite)
- [ ] Presigned URLs are user-scoped (can't access other users' files)
- [ ] URL signing key is secret and rotated
- [ ] Presigned URLs use HTTPS in production
- [ ] No presigned URLs for sensitive admin operations

### Search Patterns

```bash
# Presigned URL generation
Grep: generate_presigned_url|generate_url|upload_url|download_url
Path: agents/storage/

# Expiry configuration
Grep: S3_PRESIGNED_EXPIRY|Expires|expiry|presigned.*timeout|max_age
Path: agents/storage/ .env.example

# URL construction
Grep: f"http|http://{url}|https://
Path: agents/storage/
```

### Test Cases

```python
# Test 1: Presigned URL expiry
# 1. Generate presigned upload URL with expiry=1 second
# 2. Wait 2 seconds
# 3. Try to upload using expired URL
# Expected: 403 Forbidden

# Test 2: URL tampering
# 1. Generate presigned upload URL
# 2. Modify signature parameter
# 3. Try to upload with modified URL
# Expected: 403 Forbidden

# Test 3: Cross-user access
# 1. User A generates upload URL
# 2. User B tries to use User A's URL
# Expected: Should work (URL is bound to key, not user - verify this is intended)
```

### Configuration Check

```bash
# Check presigned URL expiry setting
grep "S3_PRESIGNED_EXPIRY" .env.example docker-compose.yml

# Recommended values:
# Development: 3600 (1 hour)
# Production: 300-900 (5-15 minutes)
```

---

## Bucket Security

### Check Points

- [ ] Bucket not publicly accessible (no public read/write)
- [ ] Bucket policy restricts access to specific users/IPs
- [ ] Versioning enabled (optional, for recovery)
- [ ] Encryption at rest enabled (if using AWS S3)
- [ ] Access logging enabled (if using AWS S3)

### Search Patterns

```bash
# Bucket creation/policy
Grep: create_bucket|bucket_policy|Policy|public
Path: agents/storage/ docker-compose.yml

# Public access (DANGEROUS in production)
Grep: "anonymous set public"|public-read|public-write
Path: docker-compose.yml scripts/
```

### MinIO-Specific Checks

```bash
# Check minio-init container
grep "mc anonymous set" docker-compose.yml

# Current implementation (from docker-compose.yml):
# mc anonymous set public local/agents
# ⚠️  WARNING: Bucket is public for development
# Fix for production: Remove this line, use user-scoped access
```

### Secure Configuration (Production)

```yaml
# BAD: Public bucket
minio-init:
  entrypoint: |
    /bin/sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin;
      mc mb local/agents --ignore-existing;
      mc anonymous set public local/agents;  # ⚠️ DANGEROUS
    "

# GOOD: Private bucket with presigned URLs only
minio-init:
  entrypoint: |
    /bin/sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin;
      mc mb local/agents --ignore-existing;
      mc admin user add local appuser apppassword;
      mc admin policy attach local readwrite --user appuser;
    "
```

---

## Access Control

### Check Points

- [ ] User-scoped access (users can only access their own files)
- [ ] No directory traversal in object keys
- [ ] No access to system bucket metadata
- [ ] API credentials restricted (least privilege)

### Search Patterns

```bash
# Object key generation
Grep: key.*=|object_key|upload_key|file_path|file_key
Path: agents/api/routes/files.py agents/storage/

# User scoping
Grep: user_id|current_user\.id|scoped.*key
Path: agents/api/routes/files.py

# Directory traversal prevention
Grep: \.\./|\.\.|path.*normalize|sanitize.*key
Path: agents/api/routes/files.py
```

### Test Cases

```python
# Test 1: Directory traversal attempt
POST /files/upload
{"filename": "../../etc/passwd", "content_type": "text/csv"}
# Expected: 400 Bad Request (filename sanitized)

# Test 2: Access another user's file
# 1. User A uploads file at: uploads/user-a/file.csv
# 2. User B tries to download: uploads/user-a/file.csv
# Expected: 404 or 403 (access denied)

# Test 3: Bucket metadata access
# Try to list all objects in bucket via API (without user scope)
# Expected: 403 (not allowed)
```

### User-Scoped Access Pattern

```python
# GOOD: User-scoped access
async def generate_upload_key(user_id: str, filename: str) -> str:
    # Sanitize filename
    safe_filename = sanitize_filename(filename)
    # User-scoped path
    return f"uploads/{user_id}/{safe_filename}"

# BAD: No user scoping
async def generate_upload_key(filename: str) -> str:
    return f"uploads/{filename}"  # Users could overwrite each other's files
```

---

## File Upload Security

### Check Points

- [ ] File size limits enforced
- [ ] File type validation (MIME type, not just extension)
- [ ] Malicious file types blocked (.exe, .php, .sh, etc.)
- [ ] File content validated (not just headers)
- [ ] No script execution from uploaded files

### Search Patterns

```bash
# File size limits
Grep: max_size|MAX_UPLOAD|MAX_FILE_SIZE|content_length|max_length
Path: agents/api/routes/files.py

# File type validation
Grep: content_type|file.*type|validate.*file|extension|mime
Path: agents/api/routes/files.py

# Allowed file types
Grep: ALLOWED_TYPES|accept.*type|valid.*extension
Path: agents/api/routes/files.py agents/api/schemas.py
```

### Test Cases

```python
# Test 1: Oversized file
# Try to upload 1GB file when limit is 100MB
# Expected: 413 Payload Too Large

# Test 2: Malicious file type with valid extension
POST /files/upload
{"filename": "malware.exe", "content_type": "application/csv"}
# Expected: 400 (type mismatch with extension)

# Test 3: Webshell upload
POST /files/upload
{"filename": "webshell.php", "content_type": "text/plain"}
# Expected: 400 (malicious extension blocked)
```

### Secure Upload Implementation

```python
# Example: File upload validation
ALLOWED_EXTENSIONS = {".csv", ".json", ".jsonl", ".txt"}
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/json",
    "application/jsonlines",
    "text/plain",
}

async def validate_file_upload(filename: str, content_type: str) -> bool:
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="File type not allowed")

    # Check MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="MIME type not allowed")

    return True
```

---

## File Download Security

### Check Points

- [ ] Users can only download their own files
- [ ] Download URLs scoped to user (or verified)
- [ ] No path traversal in download requests
- [ ] Sensitive metadata not exposed
- [ ] Rate limiting on downloads

### Search Patterns

```bash
# Download endpoints
Grep: download|get.*file|return.*file
Path: agents/api/routes/files.py

# Ownership validation
Grep: user_id.*==|where.*user_id|current_user\.id
Path: agents/api/routes/files.py

# Path traversal prevention
Grep: \.\./|\.\.|path.*normalize|sanitize.*key
Path: agents/api/routes/files.py
```

---

## Encryption

### Check Points

- [ ] TLS/HTTPS for all S3 API calls
- [ ] Encryption at rest enabled (if using AWS S3)
- [ ] Encryption in transit (HTTPS)
- [ ] No plaintext credentials in URL (use presigned URLs or headers)

### Search Patterns

```bash
# S3 endpoint configuration
Grep: S3_ENDPOINT_URL|endpoint_url|https://|http://
Path: agents/storage/ .env.example

# AWS encryption (if applicable)
Grep: SSE-S3|SSE-KMS|ServerSideEncryption
Path: agents/storage/
```

---

## Credential Management

### Check Points

- [ ] AWS credentials not hardcoded
- [ ] Credentials from environment variables
- [ ] Credentials rotated regularly
- [ ] Least privilege IAM policies (if using AWS)
- [ ] No access key in logs

### Search Patterns

```bash
# Hardcoded credentials (BAD)
Grep: (AWS_ACCESS_KEY|AWS_SECRET|MINIO_ROOT).*[:=].*['\"][^$\{]
Path: agents/ docker-compose.yml .env.example

# Environment variable usage (GOOD)
Grep: os\.getenv|getenv|os\.environ
Path: agents/storage/

# Credentials in logs (BAD)
Grep: logger\..*AWS_SECRET|logger\..*MINIO_ROOT
Path: agents/
```

### Test Cases

```python
# Test: Credentials not leaked in logs
# 1. Upload a file
# 2. Check application logs
# 3. Verify no AWS_SECRET_KEY or MINIO_ROOT_PASSWORD appears
```

---

## Container Security (MinIO)

### Check Points

- [ ] MinIO container not running as root
- [ ] MinIO credentials changed from defaults
- [ ] Data volume mounted securely
- [ ] Network isolation from other services

### Search Patterns

```bash
# MinIO container configuration
Grep: image:.*minio|MINIO_ROOT|MINIO_PASSWORD|user:
Path: docker-compose.yml

# Default credentials (BAD in production)
Grep: minioadmin
Path: docker-compose.yml .env.example
```

### Secure MinIO Configuration (Production)

```yaml
# BAD: Default credentials
minio:
  environment:
    MINIO_ROOT_USER: minioadmin
    MINIO_ROOT_PASSWORD: minioadmin

# GOOD: Strong credentials
minio:
  environment:
    MINIO_ROOT_USER: ${MINIO_ADMIN_USER}
    MINIO_ROOT_PASSWORD: ${MINIO_ADMIN_PASSWORD}
```

---

## Quick S3/MinIO Security Scan

```bash
# Run all S3/MinIO security checks
echo "=== S3/MinIO Security Scan ===" && \
echo "\n--- Presigned URL Expiry ---" && \
grep "S3_PRESIGNED_EXPIRY" .env.example && echo "Check expiry value" || echo "Set expiry time" && \
echo "\n--- Public Bucket Access ---" && \
grep "anonymous set public" docker-compose.yml && echo "WARN: Bucket is public" || echo "OK" && \
echo "\n--- Default Credentials ---" && \
grep "minioadmin" docker-compose.yml .env.example && echo "WARN: Default credentials" || echo "OK" && \
echo "\n--- Hardcoded S3 Credentials ---" && \
grep -rE "(AWS_SECRET|MINIO_ROOT|MINIO_PASSWORD).*[:=].*['\"][^$\{]" agents/ && echo "WARN: Hardcoded credentials" || echo "OK"
```

## Priority Summary

| # | Area | Priority | Status |
|---|-------|----------|--------|
| 1 | Presigned URL Expiry | P0 | [ ] |
| 2 | User-Scoped Access | P0 | [ ] |
| 3 | File Upload Validation | P0 | [ ] |
| 4 | No Public Bucket (Production) | P0 | [ ] |
| 5 | No Default Credentials | P1 | [ ] |
| 6 | TLS/HTTPS | P1 | [ ] |
| 7 | Directory Traversal Prevention | P1 | [ ] |
| 8 | File Type Validation | P1 | [ ] |
| 9 | File Size Limits | P1 | [ ] |
| 10 | Credential Management | P1 | [ ] |

## References

- [AWS S3 Security Best Practices](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
- [MinIO Security Guidelines](https://min.io/docs/minio/linux/operations/security.html)
- [OWASP Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
