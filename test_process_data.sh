#!/bin/bash

# Test script for processing vocabulary data with agents
# This script processes Chinese vocabulary data and generates study notes

set -e  # Exit on error

echo "=========================================="
echo "Agents Data Processing Test Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Make sure OPENAI_API_KEY is set in environment or .env file${NC}"
fi

# Set input and output files
# Using a test file with flat array structure
INPUT_FILE="data/test_vocab.json"
OUTPUT_FILE="data/output_processed.json"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file $INPUT_FILE not found!"
    exit 1
fi

echo "Input file: $INPUT_FILE"
echo "Output file: $OUTPUT_FILE"
echo ""

# Create a prompt for processing Chinese vocabulary
# The prompt will work with the fields available in vocabulary_light.json
# Fields: id, hanzi, pinyin, translations (array)
PROMPT="Create a detailed study note for this Chinese vocabulary word.

Word: {hanzi}
Pinyin: {pinyin}
Translations: {translations}

Create a simple example sentence using this word.
IMPORTANT: Provide a word-by-word mapping of the example sentence to help learners understand the sentence structure.

Return as JSON with keys:
- word
- pinyin
- mainTranslation
- example: object containing:
    - chinese: full Chinese sentence
    - pinyin: full Pinyin for the sentence
    - english: full English translation
    - mapping: array of objects, where each object represents a word/phrase in the sentence with keys {{chinese, pinyin, english_meaning}}.
- studyTip"

echo "Processing vocabulary data..."
echo "Prompt: $PROMPT"
echo ""

# Run the agents CLI using uv run
# Using vocabulary_light.json which has a simpler structure
# We'll process the first few items to test
uv run agents process "$INPUT_FILE" "$OUTPUT_FILE" \
    --prompt "$PROMPT" \
    --model "gpt-4o-mini" \
    --mode "sequential" \
    || {
        echo ""
        echo -e "${YELLOW}Note: If you see an error about API key, make sure OPENAI_API_KEY is set in .env file${NC}"
        exit 1
    }

echo ""
echo -e "${GREEN}=========================================="
echo "Processing complete!"
echo "==========================================${NC}"
echo ""
echo "Results saved to: $OUTPUT_FILE"
echo ""

# Check if output file was created
if [ -f "$OUTPUT_FILE" ]; then
    echo "Output file size: $(wc -l < "$OUTPUT_FILE") lines"
    echo ""
    echo "First few lines of output:"
    head -n 20 "$OUTPUT_FILE"
else
    echo "Warning: Output file was not created"
fi

