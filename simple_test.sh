#!/bin/bash

# Simple test script for processing translation data
set -e

echo "Running simple test..."

# Create test directory
mkdir -p tmp/test_run

# Create a simple test case
echo 'key,en,es' > tmp/minimal_test.csv
echo '"greeting","Hello",""' >> tmp/minimal_test.csv

# Run on minimal sample data with raw result included
uv run agents process "tmp/minimal_test.csv" "tmp/test_run/output.csv" \
    --prompt 'You are a translator. The key is {key}. The English text is "{en}". Translate this to Spanish. Return ONLY this exact JSON: {"translations": {"es": "Hola"}}' \
    --model "gpt-4o-mini" \
    --include-raw \
    --preview 1

echo "Test complete. Check tmp/test_run/output.csv for results."
