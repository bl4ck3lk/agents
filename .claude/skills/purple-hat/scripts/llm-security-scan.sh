#!/bin/bash
# LLM Security Scan for Agents Platform
# Checks for LLM-specific vulnerabilities

set -e

echo "=================================================="
echo "  LLM Security Scan - OWASP LLM Top 10"
echo "=================================================="
echo ""

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

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

echo "--- LLM01: Prompt Injection ---"
echo "Checking prompt template construction..."
PROMPT_TEMPLATE=$(grep -rE "PromptTemplate|\.render\(" agents/core/ 2>/dev/null || true)
if [ -n "$PROMPT_TEMPLATE" ]; then
    check_result "Prompt templates used" "PASS"
else
    check_result "No prompt templates found" "WARN" "MEDIUM"
fi

echo "Checking for inline system prompts..."
INLINE_PROMPT=$(grep -rE "system.*=.*\"\"\"\"|SYSTEM_PROMPT.*=|You are.*an AI|instructions.*:" agents/core/ 2>/dev/null || true)
if [ -z "$INLINE_PROMPT" ]; then
    check_result "No hardcoded system prompts" "PASS"
else
    check_result "System prompts hardcoded" "WARN" "HIGH"
    echo "$INLINE_PROMPT" | head -3
fi

echo ""
echo "--- LLM02: Sensitive Information Disclosure ---"
echo "Checking for prompt logging at INFO level..."
PROMPT_LOG=$(grep -rE "logger\.(info|warning).*prompt|log\.(info|warning).*prompt" agents/core/ 2>/dev/null || true)
if [ -z "$PROMPT_LOG" ]; then
    check_result "No prompt logging at INFO/WARNING" "PASS"
else
    check_result "Prompts logged at INFO/WARNING level" "FAIL" "HIGH"
    echo "$PROMPT_LOG"
fi

echo "Checking for secrets in prompts..."
SECRETS_IN_PROMPT=$(grep -rE "api_key.*prompt|secret.*prompt|password.*prompt" agents/core/ 2>/dev/null || true)
if [ -z "$SECRETS_IN_PROMPT" ]; then
    check_result "No secrets in prompts" "PASS"
else
    check_result "Secrets found in prompts" "FAIL" "CRITICAL"
    echo "$SECRETS_IN_PROMPT"
fi

echo ""
echo "--- LLM03: Supply Chain ---"
echo "Checking LLM client initialization..."
LLM_CLIENT=$(grep -rE "OpenAI\(|Anthropic\(|openai\.|anthropic\." agents/core/ 2>/dev/null || true)
if [ -n "$LLM_CLIENT" ]; then
    check_result "LLM client configured" "PASS"
else
    check_result "No LLM client found" "WARN" "HIGH"
fi

echo "Checking for unpinned models..."
UNPINNED_MODEL=$(grep -rE "model.*=.*['\"]latest['\"]|model.*=.*['\"]gpt-[34]['\"]|model.*=.*['\"]claude-[34]['\"]" agents/ 2>/dev/null || true)
if [ -z "$UNPINNED_MODEL" ]; then
    check_result "Models are pinned to specific versions" "PASS"
else
    check_result "Unpinned models found (using latest or version prefix)" "WARN" "MEDIUM"
    echo "$UNPINNED_MODEL"
fi

echo ""
echo "--- LLM04: Data and Model Poisoning ---"
echo "Checking for LLM output validation..."
OUTPUT_VALIDATION=$(grep -rE "extract_json|parse.*json|try:.*except.*json|model_validate" agents/core/postprocessor.py 2>/dev/null || true)
if [ -n "$OUTPUT_VALIDATION" ]; then
    check_result "LLM output validation implemented" "PASS"
else
    check_result "No LLM output validation found" "FAIL" "CRITICAL"
fi

echo ""
echo "--- LLM05: Improper Output Handling ---"
echo "Checking for max_tokens configuration..."
MAX_TOKENS=$(grep -rE "max_tokens|DEFAULT_MAX_TOKENS" agents/core/llm_client.py agents/utils/config.py 2>/dev/null || true)
if [ -n "$MAX_TOKENS" ]; then
    check_result "max_tokens configured" "PASS"
    echo "$MAX_TOKENS"
else
    check_result "No max_tokens configuration found" "FAIL" "HIGH"
fi

echo "Checking for post-processing..."
POST_PROCESS=$(grep -rE "post_process|_strip_|_sanitize" agents/core/postprocessor.py 2>/dev/null || true)
if [ -n "$POST_PROCESS" ]; then
    check_result "Post-processing implemented" "PASS"
else
    check_result "No post-processing found" "WARN" "MEDIUM"
fi

echo ""
echo "--- LLM06: Excessive Agency ---"
echo "Checking for function calling (should NOT exist in current implementation)..."
FUNCTION_CALLING=$(grep -rE "bind_tools|function_call|tool_choice|\.call\(" agents/core/llm_client.py 2>/dev/null || true)
if [ -z "$FUNCTION_CALLING" ]; then
    check_result "No function calling/tool use (SAFE)" "PASS"
else
    check_result "Function calling found - REVIEW CAREFULLY" "WARN" "HIGH"
    echo "$FUNCTION_CALLING"
fi

echo "Checking for direct DB operations from LLM context (should NOT exist)..."
LLM_DB_OPS=$(grep -rE "session\.execute|session\.add|\.commit\(" agents/core/ 2>/dev/null || true)
if [ -z "$LLM_DB_OPS" ]; then
    check_result "No direct DB operations from LLM context (SAFE)" "PASS"
else
    check_result "Direct DB operations from LLM context (DANGEROUS)" "FAIL" "CRITICAL"
    echo "$LLM_DB_OPS"
fi

echo ""
echo "--- LLM07: System Prompt Leakage ---"
echo "Checking for prompts in separate files..."
PROMPT_FILES=$(find agents/core -name "*.txt" -o -name "*.yaml" 2>/dev/null || true)
if [ -n "$PROMPT_FILES" ]; then
    check_result "Prompt files found (good practice)" "PASS"
else
    check_result "No separate prompt files found" "INFO" "LOW"
fi

echo "Checking for prompt in error messages..."
PROMPT_IN_ERROR=$(grep -rE "HTTPException.*detail.*prompt|raise.*prompt" agents/api/ 2>/dev/null || true)
if [ -z "$PROMPT_IN_ERROR" ]; then
    check_result "No prompts in error messages" "PASS"
else
    check_result "Prompts exposed in error messages" "FAIL" "HIGH"
    echo "$PROMPT_IN_ERROR"
fi

echo ""
echo "--- LLM08: Vector and Embedding Weaknesses ---"
echo "Checking for vector store/RAG implementation..."
VECTOR_STORE=$(grep -rE "Chroma|Pinecone|Weaviate|FAISS|vector.*store|embed_documents|embed_query" agents/ 2>/dev/null || true)
if [ -z "$VECTOR_STORE" ]; then
    check_result "No vector store/RAG (N/A for this implementation)" "PASS"
else
    check_result "Vector store/RAG found - review security" "INFO" "LOW"
    echo "$VECTOR_STORE" | head -3
fi

echo ""
echo "--- LLM10: Unbounded Consumption ---"
echo "Checking for file size limits..."
FILE_SIZE_LIMIT=$(grep -rE "max_file_size|MAX_UPLOAD|max_input_size" agents/api/routes/files.py 2>/dev/null || true)
if [ -n "$FILE_SIZE_LIMIT" ]; then
    check_result "File size limits configured" "PASS"
    echo "$FILE_SIZE_LIMIT"
else
    check_result "No file size limits found" "FAIL" "HIGH"
fi

echo "Checking for processing limits..."
PROCESSING_LIMITS=$(grep -rE "max_units|max_rows|max_processed" agents/processing_service/ 2>/dev/null || true)
if [ -n "$PROCESSING_LIMITS" ]; then
    check_result "Processing limits configured" "PASS"
else
    check_result "No processing limits found" "WARN" "MEDIUM"
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
    echo "❌ CRITICAL: Failed LLM security checks - address immediately!"
    echo ""
    echo "Priority Fixes:"
    echo "1. Implement LLM output validation"
    echo "2. Ensure max_tokens is configured"
    echo "3. Remove prompts from error messages"
    echo "4. Review function calling if present"
    exit 1
elif [ $WARN_COUNT -gt 3 ]; then
    echo "⚠️  WARNING: Multiple warnings - review soon"
    exit 1
else
    echo "✅ PASSED: LLM security scan completed"
    exit 0
fi
