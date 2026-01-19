# File Upload Security Checklist

Security assessment for file upload/download functionality in Agents platform.

## File Upload Validation

### Check Points

- [ ] File type validation (MIME type inspection, not just extension)
- [ ] File size limits enforced
- [ ] Allowlist of allowed file types (CSV, JSON, JSONL, TXT)
- [ ] Filename sanitization (no path traversal, no special characters)
- [ ] User-scoped upload paths (can't overwrite other users' files)

### Search Patterns

```bash
# File type validation
Grep: content_type|file.*type|validate.*file|extension|mime
Path: agents/api/routes/files.py

# File size limits
Grep: max_size|MAX_UPLOAD|max_file_size|max_input_size|content_length
Path: agents/api/routes/files.py

# Filename sanitization
Grep: sanitize.*filename|normalize.*path|validate.*filename|strip.*name
Path: agents/api/routes/files.py

# Allowed file types
Grep: ALLOWED.*TYPE|VALID.*EXTENSION|accept.*csv|accept.*json
Path: agents/api/routes/files.py agents/api/schemas.py

# User-scoped paths
Grep: user_id|current_user\.id|scoped.*path
Path: agents/api/routes/files.py

# Directory traversal prevention
Grep: \.\./|\.\.|path.*normalize|sanitize.*path|os\.path\.basename
Path: agents/api/routes/files.py
```

**Test Cases:**
```python
# Test 1: Malicious file type with valid extension
POST /files/upload
{"filename": "malware.exe", "content_type": "text/csv"}
# Expected: 400 (type mismatch)

# Test 2: Directory traversal
POST /files/upload
{"filename": "../../etc/passwd", "content_type": "text/csv"}
# Expected: 400 (path traversal detected)

# Test 3: Oversized file
# Try to upload 1GB file when limit is 100MB
# Expected: 413 Payload Too Large

# Test 4: Webshell with double extension
POST /files/upload
{"filename": "webshell.php.jpg", "content_type": "image/jpeg"}
# Expected: 400 (extension not allowed)

# Test 5: NULL byte bypass
POST /files/upload
{"filename": "malicious.php\x00.jpg", "content_type": "text/csv"}
# Expected: 400 (invalid filename)
```

### Secure Upload Implementation

```python
from pathlib import Path
from typing import Set

ALLOWED_EXTENSIONS: Set[str] = {".csv", ".json", ".jsonl", ".txt"}
ALLOWED_MIME_TYPES: Set[str] = {
    "text/csv",
    "application/json",
    "application/jsonlines",
    "text/plain",
}
MAX_FILE_SIZE_MB = 100

async def validate_file_upload(
    filename: str,
    content_type: str,
    file_size: int,
) -> str:
    """Validate file upload and return sanitized filename."""

    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed",
        )

    # Check MIME type
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type '{content_type}' not allowed",
        )

    # Check file size
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds {MAX_FILE_SIZE_MB}MB limit",
        )

    # Sanitize filename
    safe_filename = sanitize_filename(filename)
    return safe_filename


def sanitize_filename(filename: str) -> str:
    """Remove path traversal and dangerous characters."""

    # Get basename (removes directory traversal)
    safe = Path(filename).name

    # Remove dangerous characters
    safe = "".join(c for c in safe if c.isalnum() or c in "._-")

    return safe if safe else "upload"
```

---

## Presigned URL Security

### Check Points

- [ ] Presigned URL expiry time configured (5-15 minutes recommended)
- [ ] Presigned URLs are single-use (if possible)
- [ ] URL signing key is secret
- [ ] URLs use HTTPS in production
- [ ] No presigned URLs for administrative operations

### Search Patterns

```bash
# Presigned URL generation
Grep: generate_presigned_url|generate_url|upload_url|download_url
Path: agents/storage/

# Expiry configuration
Grep: S3_PRESIGNED_EXPIRY|Expires|expiry|presigned.*timeout|max_age
Path: agents/storage/ .env.example
```

**Test Cases:**
```python
# Test 1: URL expiry
# 1. Generate presigned URL with expiry=1 second
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
# Expected: Works (URL is bound to key, not user) - verify this is acceptable
```

---

## File Download Security

### Check Points

- [ ] Users can only download their own files
- [ ] Download URLs scoped to user or validated
- [ ] No path traversal in download requests
- [ ] Sensitive metadata not exposed
- [ ] Download rate limiting (optional)

### Search Patterns

```bash
# Download endpoints
Grep: download|get.*file|return.*file|FileResponse
Path: agents/api/routes/files.py

# Ownership validation on downloads
Grep: user_id.*==|where.*user_id|current_user\.id
Path: agents/api/routes/files.py

# Path traversal prevention
Grep: \.\./|\.\.|path.*normalize|sanitize.*key
Path: agents/api/routes/files.py
```

**Test Cases:**
```python
# Test 1: Download another user's file
GET /api/files/OTHER_USER_FILE_ID
Authorization: Bearer YOUR_TOKEN
# Expected: 404 (not found) or 403 (forbidden)

# Test 2: Directory traversal
GET /api/files/../../etc/passwd
Authorization: Bearer YOUR_TOKEN
# Expected: 404 (validation rejects)

# Test 3: Direct object key access
GET /api/files/uploads/other-user/file.csv
Authorization: Bearer YOUR_TOKEN
# Expected: 403 (forbidden)
```

---

## Storage Security (MinIO/S3)

### Check Points

- [ ] Bucket not publicly accessible (no public read/write in production)
- [ ] User-scoped object keys (uploads/{user_id}/{filename})
- [ ] No directory traversal in object keys
- [ ] Object access validated on download
- [ ] Encryption at rest enabled (if using AWS S3)

### Search Patterns

```bash
# Bucket policies
Grep: public-read|public-write|Policy|Allow
Path: docker-compose.yml scripts/

# Public access (DANGEROUS in production)
Grep: "anonymous set public"
Path: docker-compose.yml scripts/
```

---

## Common File Upload Vulnerabilities

### Malicious File Types

```bash
# Executables (should be blocked)
.exe, .sh, .bat, .cmd, .ps1

# Webshells (should be blocked)
.php, .asp, .aspx, .jsp, .jspx

# Dangerous documents (should be validated)
.doc, .docx, .pdf, .xls, .xlsx
```

### Filename Attacks

```bash
# Directory traversal
../../etc/passwd
..%2F..%2Fetc%2Fpasswd
....//....//....//etc/passwd

# NULL byte injection
file.php\x00.jpg

# Unicode bypass
file.php%e0%00.jpg
```

### File Size Attacks

```bash
# Oversized file (DoS)
# Upload 10GB file when limit is 100MB

# Many small files (storage exhaustion)
# Upload 10,000 small files
```

---

## Content Security

### Check Points

- [ ] File content validated (MIME type from content, not just header)
- [ ] Malicious content patterns detected (if applicable)
- [ ] No execution from upload directories
- [ ] Quarantine system for suspicious files (optional)

**Search Patterns:**
```bash
# MIME type inspection
Grep: magic|libmagic|mimetype|filetype
Path: agents/api/routes/files.py

# Content scanning (optional)
Grep: clamav|virus.*scan|malware.*detect
Path: agents/api/routes/files.py
```

---

## Quick File Upload Security Scan

```bash
# Run all file upload security checks
echo "=== File Upload Security Scan ===" && \
echo "\n--- File Type Validation ---" && \
grep -rE "content_type|ALLOWED.*TYPE|validate.*file" agents/api/routes/files.py && echo "OK" || echo "WARN: Add file type validation" && \
echo "\n--- File Size Limits ---" && \
grep -rE "max_file_size|MAX_UPLOAD|max_size|content_length" agents/api/routes/files.py && echo "OK" || echo "WARN: Add file size limits" && \
echo "\n--- Filename Sanitization ---" && \
grep -rE "sanitize.*filename|normalize.*path|basename" agents/api/routes/files.py && echo "OK" || echo "WARN: Add filename sanitization" && \
echo "\n--- User-Scoped Paths ---" && \
grep -rE "user_id|current_user\.id" agents/api/routes/files.py && echo "OK" || echo "WARN: Add user scoping" && \
echo "\n--- Public Bucket Access ---" && \
grep -rE "anonymous set public|public-read|public-write" docker-compose.yml && echo "WARN: Bucket is public" || echo "OK"
```

## Priority Summary

| # | Area | Priority | Status |
|---|-------|----------|--------|
| 1 | File Type Validation | P0 | [ ] |
| 2 | File Size Limits | P0 | [ ] |
| 3 | Filename Sanitization | P0 | [ ] |
| 4 | User-Scoped Access | P0 | [ ] |
| 5 | Path Traversal Prevention | P0 | [ ] |
| 6 | Presigned URL Expiry | P0 | [ ] |
| 7 | No Public Bucket (Production) | P0 | [ ] |
| 8 | Content Validation | P1 | [ ] |
| 9 | Download Ownership | P1 | [ ] |
| 10 | Encryption at Rest | P2 | [ ] |

## References

- [OWASP Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
- [File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [MinIO Security](https://min.io/docs/minio/linux/operations/security.html)
- [AWS S3 Security](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)
