#!/bin/bash

# Production script for processing full vocabulary data with agents
# This script processes Chinese vocabulary data from vocabulary.json and generates detailed study notes

set -e  # Exit on error

echo "=========================================="
echo "Agents Full Vocabulary Processing Script"
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

# Input and Output configuration
ORIGINAL_INPUT="data/vocabulary.json"
FLAT_INPUT="data/vocabulary_flat.json"
OUTPUT_FILE="data/vocabulary_processed.json"

# Check if input file exists
if [ ! -f "$ORIGINAL_INPUT" ]; then
    echo "Error: Input file $ORIGINAL_INPUT not found!"
    exit 1
fi

echo "Original Input: $ORIGINAL_INPUT"
echo "Flat Input (temp): $FLAT_INPUT"
echo "Output file: $OUTPUT_FILE"
echo ""

# Step 1: Flatten the input JSON
# The original file has keys like "hsk1", "hsk2" containing lists. We want one big list.
echo "Flattening input JSON..."
python3 -c "
import json
import sys

try:
    with open('$ORIGINAL_INPUT', 'r') as f:
        data = json.load(f)

    flat_list = []
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                # Inject the key as 'group' for each item to preserve structure
                for item in value:
                    if isinstance(item, dict):
                        item['group'] = key
                flat_list.extend(value)
    elif isinstance(data, list):
        flat_list = data

    with open('$FLAT_INPUT', 'w') as f:
        json.dump(flat_list, f, indent=2, ensure_ascii=False)

    print(f'Successfully flattened {len(flat_list)} items to $FLAT_INPUT')

except Exception as e:
    print(f'Error flattening JSON: {e}')
    sys.exit(1)
"

echo ""

# Step 2: Define the prompt
# Using fields from vocabulary.json: simplified, pinyin, definition
PROMPT="Create a detailed study note for this Chinese vocabulary word. Be concise and accurate.

Word: {simplified}
Pinyin: {pinyin}
Translations: {definition}

Create a simple example sentence using this word.
IMPORTANT: Provide a word-by-word mapping of the example sentence to help learners understand the sentence structure.

Return as JSON with keys:
- traditional
- partOfSpeech (is missing or wrong.)
- example
- exampleTranslation
- emoji (if, possible, add it.)
- etymology (concise and accurate.)
- relatedWords (if, possible, add it - hanzi, pinyin, main meaning(s).)
- example: object containing:
    - chinese: full Chinese sentence
    - pinyin: full Pinyin for the sentence
    - english: full English translation
    - mapping: array of objects, where each object represents a word/phrase in the sentence with keys {{chinese, pinyin, english_meaning}}.
- studyTip (concise and accurate.)"

echo "Processing vocabulary data..."
echo "Prompt: $PROMPT"
echo ""

# Step 3: Run the agents CLI
# Using async mode for better performance on large datasets
# Defaults from CLI: merge=True, include-raw=False are used implicitly
# Added --preview 3 to verify prompt performance on a few items before running full batch
uv run agents process "$FLAT_INPUT" "$OUTPUT_FILE" \
    --prompt "$PROMPT" \
    --model "gpt-4o-mini" \
    --mode "async" \
    --batch-size 20 \
    --preview 3 \
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
