#!/bin/bash

# Minimal test script
set -e

echo "Running minimal test..."

# Run on minimal sample data with raw result included
uv run agents process "minimal_test.csv" "minimal_output.csv" \
    --prompt 'You are a translator. The English text is "{en}". Translate this to Spanish. Return ONLY this JSON: {"es": "Hola"}' \
    --model "gpt-4o-mini" \
    --include-raw \
    --preview 1

echo "Test complete."
