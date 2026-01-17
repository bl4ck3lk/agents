#!/bin/bash

# Production script for processing translation data with agents
# This script processes multilingual translation data from translations.csv and fills in missing translations

set -e  # Exit on error

# Parse command line arguments
RANDOM_SAMPLES=3
SKIP_PREVIEW=false
RESUME_JOB=""
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
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -s, --skip-preview  Skip the preview step (process K random samples)"
            echo "  -r, --resume JOB_ID Resume a previous job"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                        # Run with preview"
            echo "  $0 -s                     # Run without preview"
            echo "  $0 -r job_20251127_015842 # Resume a paused job"
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
echo "Agents Translation Completion Script"
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
INPUT_FILE="data/missing_translations.csv"

# Check if input file exists
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file $INPUT_FILE not found!"
    exit 1
fi

# Create timestamped run folder
RUN_TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RUN_DIR="data/runs/run_${RUN_TIMESTAMP}"
mkdir -p "$RUN_DIR"

# Output file in run folder
OUTPUT_FILE="${RUN_DIR}/translations_completed.csv"

echo "Input: $INPUT_FILE"
echo -e "${BLUE}Run folder: $RUN_DIR${NC}"
echo "Output file: $OUTPUT_FILE"
echo ""
echo "NOTE: The output file will contain ALL translations - both existing and newly generated ones."
echo ""

# Step 1: Dynamically build the prompt with all language fields from CSV
# Read the CSV header to get all language columns and build a prompt template
echo "Reading CSV structure to build prompt template..."
PROMPT=$(INPUT_FILE="$INPUT_FILE" python3 << 'PYTHON_SCRIPT'
import csv
import os

input_file = os.environ['INPUT_FILE']

# Read CSV header to get all columns
with open(input_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    columns = reader.fieldnames or []
    
# Separate 'key' from language columns
language_cols = [col for col in columns if col != 'key']

# Build the prompt template with all language fields
prompt_parts = [
    "You are a professional localization expert specializing in iOS app translation for productivity and accessibility-focused applications. You translate with deep awareness of linguistic semantics, platform conventions, and cognitive load constraints.",
    "",
    "App Context:",
    "ichigo is an ADHD-supportive checklist iOS app built in SwiftUI. The design emphasizes low-stimuli UI, minimal ambiguity, and fast comprehension. Translations must always be:",
    "- Semantically precise (not literal unless literal is correct)",
    "- Extremely concise (lowest cognitive load)",
    "- Idiomatic for the target locale in real-world productivity apps",
    "- Consistent with iOS Human Interface Guidelines and Apple-style terminology",
    "- Consistent across related keys (headers, statuses, actions, labels)",
    "",
    "Task:",
    "Given a translation key and existing translations in various languages, infer the semantic role of the key (e.g., section header, button label, status text, empty-state message, descriptive sentence, etc.). Produce translations for ALL languages where the field is empty or contains unusable content.",
    "",
    "Input Data:",
    "- Translation Key: {key}"
]

# Add all language fields to the prompt
for lang_col in language_cols:
    # Escape braces in the language code for Python format string
    # We need to use {{ and }} to represent literal braces in the format string
    prompt_parts.append(f"- {lang_col}: {{{lang_col}}}")

prompt_parts.extend([
    "",
    "CRITICAL LOCALIZATION RULES:",
    "",
    "1. Infer the semantic category of the key.",
    "   Examples:",
    "   - \"group.overdue\" → section header (noun-like category)",
    "   - \"button.save\" → action button label (verb)",
    "   - \"error.network\" → error title (noun phrase)",
    "   - \"task.completed\" → status label (adjectival but noun-like)",
    "   You MUST translate according to the function of the string, not word-by-word.",
    "",
    "2. Produce translations that sound natural in native UI.",
    "   Not dictionary literal.",
    "   Follow real-world usage from Apple, Google, and major productivity apps.",
    "",
    "3. Placeholder Preservation:",
    "   - DO NOT modify placeholders (e.g., %@, %lld, %1$@).",
    "   - If the language requires reordering arguments (e.g., Japanese, Arabic), use positional specifiers (%1$@, %2$@, etc.).",
    "   - Never translate inside braces or parentheses tied to placeholders.",
    "",
    "4. Cultural & linguistic correctness:",
    "   - Some languages require plural or adjective agreement for category labels.",
    "   - Some languages cannot use adjectives as nouns (Slavic languages, Arabic, etc.).",
    "   - East Asian languages avoid unnecessary particles—keep concise.",
    "   - Do not force English grammatical structure into other languages.",
    "",
    "5. Consistency checks:",
    "   - Use sibling translations (if present) to maintain structural harmony.",
    "   - Preserve capitalization consistent with OS norms (e.g., English Title Case, Spanish Sentence case, Japanese no caps).",
    "   - The app name \"ichigo\" must always remain lowercase in all translations.",
    "",
    "6. Maintain simplicity for ADHD users:",
    "   - Avoid long multi-word constructions unless required by the language.",
    "   - Choose the most cognitively lightweight phrasing that remains correct.",
    "",
    "7. Quality Requirements:",
    "   - If a provided translation is incorrect, unnatural, or mismatched with UI conventions, treat it as missing and replace it.",
    "   - Never fill partial translations or machine-translated artifacts without correction.",
    "",
    "OUTPUT FORMAT:",
    "- Respond with ONLY a valid JSON object.",
    "- Keys must be the language codes with missing/incorrect translations.",
    "- Values must be the corrected translations.",
    "- No commentary, no markdown, no code fences.",
    "- CRITICAL: Do NOT wrap your response in markdown code blocks",
    "- CRITICAL: Do NOT include ```json or ``` before/after your response",
    "- CRITICAL: Start your response directly with {{ and end with }}",
    "- Use the language codes exactly as they appear in the input (e.g., \"es\", \"fr-CA\", \"zh-Hans\")",
    "- If all translations are present and correct, output exactly: {{}}",
    "",
    "Example 1:",
    "Input:",
    "- key: button.save",
    "- en: Save",
    "- es: \"\" (empty)",
    "- fr: \"\" (empty)",
    "- de: Speichern",
    "- it: Salva",
    "",
    "Output (must be valid JSON, no markdown):",
    '{{"es": "Guardar", "fr": "Sauvegarder"}}',
    "",
    "Example 2:",
    "Input:",
    "- key: group.overdue",
    "- en: Overdue",
    "- es: \"\" (empty)",
    "- fr: En retard",
    "- de: Überfällig",
    "",
    "Output (must be valid JSON, no markdown):",
    '{{"es": "Vencido"}}',
    "",
    "REMINDER: Check EVERY language field. Include ALL missing or incorrect translations in your response."
])

prompt = "\n".join(prompt_parts)
print(prompt)
PYTHON_SCRIPT
)

# Save prompt to run folder for reference
echo "$PROMPT" > "${RUN_DIR}/prompt.txt"

echo "Processing translation data to fill in missing translations..."
echo "Prompt saved to: ${RUN_DIR}/prompt.txt"
echo ""

# Step 2: Run the agents CLI
# Using async mode for better performance on large datasets
# Added --preview 3 to verify prompt performance on a few items before running full batch
# Added --checkin-interval 100 to pause every 100 entries for user confirmation

# Build command with optional preview
# Escape the prompt properly for bash - replace any problematic characters
# The prompt is saved to prompt.txt, so we can reference it if needed
# For now, use the PROMPT variable directly with proper quoting
AGENTS_CMD=(uv run agents process "$INPUT_FILE" "$OUTPUT_FILE"
    --prompt "$PROMPT"
    --model "openai/gpt-5-mini"
    --mode "async"
    --batch-size 15
    --checkin-interval 100
)

if [ "$SKIP_PREVIEW" = false ]; then
    AGENTS_CMD+=(--preview $RANDOM_SAMPLES)
    echo "Preview mode: enabled (random $RANDOM_SAMPLES samples)"
else
    echo -e "${YELLOW}Preview mode: skipped${NC}"
fi
echo ""

# Execute the command - the prompt is already properly quoted in the array
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

    # Count how many translations were filled in
    FILLED_COUNT=$(python3 << PYTHON_COUNT
import csv
count = 0
with open("$OUTPUT_FILE", 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        for key in row.keys():
            if key != 'key' and row[key]:
                count += 1
print(count)
PYTHON_COUNT
)
    echo "Total translation entries: $FILLED_COUNT"

    # Create a symlink to the latest run for convenience
    LATEST_LINK="data/runs/latest"
    rm -f "$LATEST_LINK"
    ln -s "run_${RUN_TIMESTAMP}" "$LATEST_LINK"
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
