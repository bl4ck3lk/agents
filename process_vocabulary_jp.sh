#!/bin/bash

# Production script for processing full vocabulary data with agents
# This script processes Japanese vocabulary data from vocabulary_jp.json and generates detailed study notes

set -e  # Exit on error

# Parse command line arguments
SKIP_PREVIEW=false
RESUME_JOB=""
FORCE_FLATTEN=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-preview|-s)
            SKIP_PREVIEW=true
            shift
            ;;
        --resume|-r)
            RESUME_JOB="$2"
            shift 2
            ;;
        --force-flatten|-f)
            FORCE_FLATTEN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -s, --skip-preview  Skip the preview step (process K random samples)"
            echo "  -r, --resume JOB_ID Resume a previous job"
            echo "  -f, --force-flatten Re-flatten the input file even if cached version exists"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                        # Run with preview"
            echo "  $0 -s                     # Run without preview"
            echo "  $0 -r job_20251127_015842 # Resume a paused job"
            echo "  $0 -f                     # Force re-flatten input file"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Handle resume mode
if [ -n "$RESUME_JOB" ]; then
    echo "Resuming job: $RESUME_JOB"
    uv run agents resume "$RESUME_JOB" --checkin-interval 100
    exit $?
fi

echo "=========================================="
echo "Agents Full Japanese Vocabulary Processing Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found. Make sure OPENAI_API_KEY is set in environment or .env file${NC}"
fi

# Input configuration
ORIGINAL_INPUT="data/vocabulary_jp.json"
FLAT_INPUT="data/vocabulary_jp_flat.json"

# Check if input file exists
if [ ! -f "$ORIGINAL_INPUT" ]; then
    echo "Error: Input file $ORIGINAL_INPUT not found!"
    exit 1
fi

# Create timestamped run folder
RUN_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RUN_DIR="data/runs/run_jp_${RUN_TIMESTAMP}"
mkdir -p "$RUN_DIR"

# Output file in run folder
OUTPUT_FILE="${RUN_DIR}/vocabulary_jp_processed.json"

echo "Original Input: $ORIGINAL_INPUT"
echo "Flat Input (cached): $FLAT_INPUT"
echo -e "${BLUE}Run folder: $RUN_DIR${NC}"
echo "Output file: $OUTPUT_FILE"
echo ""

# Step 1: Flatten the input JSON (skip if already exists, unless --force-flatten)
# The original file has keys like "jlpt_n5", "jlpt_n4" containing lists. We want one big list.
if [ -f "$FLAT_INPUT" ] && [ "$FORCE_FLATTEN" = false ]; then
    echo -e "${GREEN}Flat input file already exists, skipping flattening step${NC}"
    ITEM_COUNT=$(python3 -c "import json; print(len(json.load(open('$FLAT_INPUT'))))")
    echo "Flat file contains $ITEM_COUNT items"
else
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
fi

echo ""

# Step 2: Define the prompt
# Using fields from vocabulary_jp.json: word, reading, definition
PROMPT="
You're a helpful Japanese language assistant that will help students learn and memorize Japanese vocabulary (JLPT levels N5-N1).
Create a helpful study note for this Japanese vocabulary word. Be concise and accurate.
Answers must not have any typos or grammatical errors. Also limited to a maximum of 1500 total output tokens.

Word: {word}
Reading: {reading}
Translations: {definition}

Create a simple example sentence using this word.
IMPORTANT: Provide a word-by-word mapping of the example sentence to help learners understand the sentence structure.

Return as JSON with keys:
- kanji (the kanji form if applicable, otherwise same as word)
- partOfSpeech (noun, verb, adjective, adverb, particle, etc.)
- example (use the word form provided! It must contain {word})
- exampleTranslation
- emoji (if possible, add it. Multiples (Min. 1, Max. 5) if necessary to express the meaning.)
- etymology (concise and accurate. If you don't know for sure, leave it blank.)
- relatedWords (if possible, add related words - word, reading, main meaning(s))
- example: object containing:
    - japanese: full Japanese sentence
    - reading: full reading (hiragana/katakana) for the sentence
    - english: full English translation
    - mapping: array of objects, where each object represents a word/phrase in the sentence with keys {{japanese, reading, english_meaning}}.
- studyTip (very concise and accurate. Add good mnemonics to help learners remember the word. Consider kanji radicals, sound associations, or visual cues.)"

# Save prompt to run folder for reference
echo "$PROMPT" > "${RUN_DIR}/prompt.txt"

echo "Processing Japanese vocabulary data..."
echo "Prompt saved to: ${RUN_DIR}/prompt.txt"
echo ""

# Step 3: Run the agents CLI
# Using async mode for better performance on large datasets
# Defaults from CLI: merge=True, include-raw=False are used implicitly
# Added --preview 3 to verify prompt performance on a few items before running full batch
# Added --checkin-interval 100 to pause every 100 entries for user confirmation

# Build command with optional preview
AGENTS_CMD=(uv run agents process "$FLAT_INPUT" "$OUTPUT_FILE"
    --prompt "$PROMPT"
    --model "deepseek/deepseek-v3.1-terminus"
    --mode "async"
    --batch-size 20
    --checkin-interval 100
)

if [ "$SKIP_PREVIEW" = false ]; then
    AGENTS_CMD+=(--preview 3)
    echo "Preview mode: enabled (3 random samples)"
else
    echo -e "${YELLOW}Preview mode: skipped${NC}"
fi
echo ""

"${AGENTS_CMD[@]}"
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}Note: If you see an error about API key, make sure OPENAI_API_KEY is set in .env file${NC}"
    exit 1
fi

echo ""

# Check if output file was created (indicates completion vs pause)
if [ -f "$OUTPUT_FILE" ]; then
    echo -e "${GREEN}=========================================="
    echo "Processing complete!"
    echo "==========================================${NC}"
    echo ""
    echo -e "Run folder: ${BLUE}$RUN_DIR${NC}"
    echo "Results saved to: $OUTPUT_FILE"
    echo ""
    echo "Output file size: $(wc -l < "$OUTPUT_FILE") lines"

    # Create a symlink to the latest run for convenience
    LATEST_LINK="data/runs/latest_jp"
    rm -f "$LATEST_LINK"
    ln -s "run_jp_${RUN_TIMESTAMP}" "$LATEST_LINK"
    echo ""
    echo -e "Latest run symlink: ${BLUE}$LATEST_LINK${NC}"
else
    echo -e "${YELLOW}=========================================="
    echo "Job paused - output file not yet created"
    echo "==========================================${NC}"
    echo ""
    echo "To resume this job, use the job ID shown above:"
    echo -e "  ${BLUE}agents resume <job_id>${NC}"
    echo ""
    echo "To check progress, look in .checkpoints/ folder"
fi
