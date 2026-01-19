#!/bin/bash
# Quick Security Scan for Agents Platform
# Rapid security audit for common vulnerabilities

set -e

echo "=================================================="
echo "  Agents Platform - Quick Security Scan"
echo "=================================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# Function to check and report
check_result() {
    local name="$1"
    local result="$2"
    local severity="$3"

    if [ "$result" == "PASS" ]; then
        echo "✓ $name"
        ((PASS_COUNT++))
    elif [ "$result" == "FAIL" ]; then
        echo "✗ $name [$severity]"
        ((FAIL_COUNT++))
    else
        echo "⚠ $name [$severity]"
        ((WARN_COUNT++))
    fi
}

echo "--- Hardcoded Secrets ---"
SECRETS=$(grep -rE "(password|secret|api_key|token)\s*=\s*[\"'][^$\{]" agents/ 2>/dev/null || true)
if [ -z "$SECRETS" ]; then
    check_result "No hardcoded secrets" "PASS"
else
    check_result "Possible hardcoded secrets found" "FAIL" "CRITICAL"
    echo "$SECRETS"
fi

echo ""
echo "--- SQL Injection Vectors ---"
SQL_INJ=$(grep -rE "execute\(.*%|text\(.*\+|text\(.*format|\.raw\(" agents/db/ 2>/dev/null || true)
if [ -z "$SQL_INJ" ]; then
    check_result "No obvious SQL injection vectors" "PASS"
else
    check_result "Possible SQL injection vectors" "FAIL" "CRITICAL"
    echo "$SQL_INJ"
fi

echo ""
echo "--- Command Injection Vectors ---"
CMD_INJ=$(grep -rE "subprocess|os\.system|shell=True|eval\(|exec\(" agents/ 2>/dev/null || true)
# Filter out imports and comments (false positives)
CMD_INJ=$(echo "$CMD_INJ" | grep -vE "^(import |from |#)" || true)
if [ -z "$CMD_INJ" ]; then
    check_result "No obvious command injection vectors" "PASS"
else
    check_result "Possible command injection vectors" "WARN" "HIGH"
    echo "$CMD_INJ" | head -5
fi

echo ""
echo "--- Debug Mode ---"
DEBUG=$(grep -rE "DEBUG.*=.*True|--reload|--debug|RELOAD.*=.*true" agents/ docker-compose*.yml 2>/dev/null || true)
if [ -z "$DEBUG" ]; then
    check_result "No debug mode in production files" "PASS"
else
    check_result "Debug mode or reload found" "WARN" "HIGH"
    echo "$DEBUG"
fi

echo ""
echo "--- Default Credentials ---"
DEFAULT_CREDS=$(grep -rE "minioadmin|postgres:postgres|dev-secret-key" docker-compose*.yml 2>/dev/null || true)
if [ -z "$DEFAULT_CREDS" ]; then
    check_result "No default credentials in docker-compose" "PASS"
else
    check_result "Default credentials found in docker-compose" "WARN" "HIGH"
    echo "$DEFAULT_CREDS"
fi

echo ""
echo "--- API Key Encryption ---"
ENCRYPTION=$(grep -r "APIKeyEncryption\|Fernet\|encrypt" agents/api/ 2>/dev/null || true)
if [ -n "$ENCRYPTION" ]; then
    check_result "API key encryption implemented" "PASS"
else
    check_result "No API key encryption found" "FAIL" "CRITICAL"
fi

echo ""
echo "--- Rate Limiting ---"
RATE_LIMIT=$(grep -r "@limiter\.limit\|slowapi\|RateLimiter" agents/api/ 2>/dev/null || true)
if [ -n "$RATE_LIMIT" ]; then
    check_result "Rate limiting implemented" "PASS"
else
    check_result "No rate limiting found" "WARN" "HIGH"
fi

echo ""
echo "--- Authentication Dependencies ---"
AUTH=$(grep -r "Depends\(current" agents/api/routes/ 2>/dev/null || true)
if [ -n "$AUTH" ]; then
    check_result "Authentication dependencies used" "PASS"
else
    check_result "Missing authentication on endpoints" "FAIL" "CRITICAL"
fi

echo ""
echo "--- CORS Configuration ---"
CORS_WILDCARD=$(grep -rE "allow_origins.*\*|allow_origins.*\[\"\*\"" agents/api/ 2>/dev/null || true)
if [ -z "$CORS_WILDCARD" ]; then
    check_result "CORS not set to wildcard" "PASS"
else
    check_result "CORS set to wildcard (*)" "WARN" "MEDIUM"
    echo "$CORS_WILDCARD"
fi

echo ""
echo "--- Security Headers ---"
HEADERS=$(grep -rE "X-Content-Type|X-Frame-Options|Content-Security-Policy|HSTS" agents/api/ 2>/dev/null || true)
if [ -n "$HEADERS" ]; then
    check_result "Security headers configured" "PASS"
else
    check_result "No security headers found" "WARN" "MEDIUM"
fi

echo ""
echo "--- Prompt Logging ---"
PROMPT_LOG=$(grep -rE "logger\.(info|warning).*prompt" agents/ 2>/dev/null || true)
if [ -z "$PROMPT_LOG" ]; then
    check_result "No prompt logging at INFO level" "PASS"
else
    check_result "Prompts logged at INFO level" "WARN" "MEDIUM"
    echo "$PROMPT_LOG"
fi

echo ""
echo "--- Dependency Audit ---"
echo "Checking for outdated dependencies..."
if command -v uv &> /dev/null; then
    uv pip list --outdated 2>/dev/null | head -10
elif command -v pip &> /dev/null; then
    pip list --outdated 2>/dev/null | head -10
else
    echo "⚠ Neither uv nor pip found, skipping dependency check"
    ((WARN_COUNT++))
fi

echo ""
echo "=================================================="
echo "  Summary"
echo "=================================================="
echo "✓ Passed:  $PASS_COUNT"
echo "✗ Failed:  $FAIL_COUNT"
echo "⚠ Warnings: $WARN_COUNT"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    echo "❌ CRITICAL: Failed checks found - address immediately!"
    exit 1
elif [ $WARN_COUNT -gt 3 ]; then
    echo "⚠️  WARNING: Multiple warnings - review soon"
    exit 1
else
    echo "✅ PASSED: Quick security scan completed successfully"
    exit 0
fi
