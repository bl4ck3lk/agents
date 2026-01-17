#!/bin/bash

# Test script for fixed translation processing
set -e

echo "Running test with fixed script..."

# Create test directory
mkdir -p tmp/test_run_fixed

# Run on sample data with fixed prompt and no post-processing
uv run agents process "tmp/test_with_translations_fixed.csv" "tmp/test_run_fixed/output.csv" \
    --prompt 'You are a translator. The key is {key}. English: "{en}", German: "{de}", French: "{fr}". Provide missing Spanish translation. Return ONLY this JSON: {"es": "translated text"}' \
    --model "gpt-4o-mini" \
    --no-post-process \
    --preview 1

echo "Test complete. Check tmp/test_run_fixed/output.csv for results."
