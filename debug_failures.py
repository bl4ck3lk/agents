#!/usr/bin/env python3
"""Debug script to analyze failures and show why they failed."""

import json
import sys
from pathlib import Path


def analyze_failure(failure_data: dict) -> None:
    """Analyze a single failure and print debugging information."""
    print("=" * 80)
    print(f"Key: {failure_data.get('key', 'N/A')}")
    print(f"Index: {failure_data.get('_idx', 'N/A')}")
    
    # Check error type
    if "parse_error" in failure_data:
        print(f"Error Type: Parse Error")
        print(f"  Message: {failure_data['parse_error']}")
    elif "error" in failure_data:
        print(f"Error Type: Fatal Error")
        print(f"  Message: {failure_data['error']}")
    else:
        print("Error Type: Unknown")
    
    print(f"Retries Exhausted: {failure_data.get('_retries_exhausted', False)}")
    print(f"Attempts: {failure_data.get('_attempts', 'N/A')}")
    
    # Show raw output - check both fields, handling empty strings
    raw_output = None
    if "_raw_output" in failure_data:
        raw_output = failure_data["_raw_output"]
    elif "result" in failure_data:
        raw_output = failure_data["result"]
    
    print(f"\n{'=' * 80}")
    print("Raw LLM Output Analysis:")
    print("-" * 80)
    
    if raw_output is None:
        print("⚠️  No raw output field found")
        print("  💡 This failure occurred before the _raw_output fix was applied")
    elif raw_output == "":
        print("❌ LLM returned EMPTY response")
        print("  💡 This means the LLM API returned an empty string")
        print("  💡 Possible reasons:")
        print("     - API rate limit or quota exceeded")
        print("     - Model returned empty (rare)")
        print("     - Network/timeout issue")
        print("     - API error that wasn't caught")
    else:
        print(f"Raw Output ({len(raw_output)} chars):")
        print("-" * 80)
        print(raw_output)
        print("-" * 80)
        
        # Try to identify why parsing failed
        print("\nAnalysis:")
        if not raw_output.strip():
            print("  ❌ Response is empty or only whitespace")
        elif raw_output.strip().startswith("```"):
            print("  ⚠️  Response wrapped in markdown code blocks")
            print("  💡 The postprocessor should handle this, but may have failed")
            # Try to extract JSON from markdown
            import re
            match = re.search(r"```(?:json)?\s*\n(.*?)\n```", raw_output, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                try:
                    parsed = json.loads(json_str)
                    print(f"  ✅ Found valid JSON in markdown! Keys: {list(parsed.keys())[:5]}")
                except:
                    print(f"  ❌ JSON in markdown is invalid")
        elif not raw_output.strip().startswith("{"):
            print("  ❌ Response doesn't start with '{'")
            print(f"  💡 First 200 chars: {repr(raw_output[:200])}")
        elif not raw_output.strip().endswith("}"):
            print("  ⚠️  Response doesn't end with '}'")
            print("  💡 Response may be truncated")
            print(f"  💡 Last 200 chars: {repr(raw_output[-200:])}")
        else:
            print("  ✅ Response looks like JSON")
            # Try to parse it
            try:
                parsed = json.loads(raw_output.strip())
                print(f"  ✅ Actually valid JSON! Keys: {list(parsed.keys())[:5]}")
                print(f"  ⚠️  But postprocessor failed to parse it - this is a bug!")
            except json.JSONDecodeError as e:
                print(f"  ❌ JSON parsing error: {e}")
                print(f"  💡 Error at position {e.pos}")
                if e.pos < len(raw_output):
                    start = max(0, e.pos - 50)
                    end = min(len(raw_output), e.pos + 50)
                    print(f"  💡 Context around error: {repr(raw_output[start:end])}")
    
    # Show input context
    print(f"\n{'=' * 80}")
    print("Input Context (non-empty fields):")
    non_empty = {k: v for k, v in failure_data.items() 
                 if k not in ['_idx', '_retries_exhausted', '_attempts', 
                             'parse_error', 'error', '_raw_output', 'result'] 
                 and v}
    if non_empty:
        for k, v in list(non_empty.items())[:10]:
            print(f"  {k}: {repr(v)}")
    else:
        print("  (All translation fields are empty)")
    
    print("=" * 80)


def check_checkpoint_file(job_id: str, failure_key: str, failure_idx: int) -> None:
    """Check the checkpoint results file for all attempts at this failure."""
    checkpoint_file = Path(f".checkpoints/.results_{job_id}.jsonl")
    if not checkpoint_file.exists():
        return
    
    print(f"\n{'=' * 80}")
    print("Checking checkpoint file for all retry attempts:")
    print(f"  File: {checkpoint_file}")
    print("-" * 80)
    
    attempts = []
    with open(checkpoint_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if line.strip():
                try:
                    data = json.loads(line)
                    if data.get('key') == failure_key and data.get('_idx') == failure_idx:
                        attempts.append((line_num, data))
                except:
                    pass
    
    if attempts:
        print(f"Found {len(attempts)} attempt(s) in checkpoint file:\n")
        for i, (line_num, attempt_data) in enumerate(attempts, 1):
            print(f"Attempt #{i} (line {line_num}):")
            raw = attempt_data.get("_raw_output") or attempt_data.get("result")
            if raw is not None:
                if raw == "":
                    print(f"  ❌ Empty response")
                else:
                    print(f"  Response length: {len(raw)} chars")
                    print(f"  First 100 chars: {repr(raw[:100])}")
            else:
                print(f"  ⚠️  No raw output")
            print()
    else:
        print("No attempts found in checkpoint file")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 debug_failures.py <failures_file.jsonl> [--check-checkpoint]")
        print("\nExample:")
        print("  python3 debug_failures.py .checkpoints/failures_job_20251204_190508.jsonl")
        print("  python3 debug_failures.py .checkpoints/failures_job_20251204_190508.jsonl --check-checkpoint")
        sys.exit(1)
    
    failures_file = Path(sys.argv[1])
    check_checkpoint = "--check-checkpoint" in sys.argv
    
    if not failures_file.exists():
        print(f"Error: File not found: {failures_file}")
        sys.exit(1)
    
    print(f"Analyzing failures from: {failures_file}\n")
    
    failures = []
    with open(failures_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    failures.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Failed to parse line: {e}")
    
    if not failures:
        print("No failures found in file.")
        return
    
    print(f"Found {len(failures)} failure(s)\n")
    
    # Analyze each failure
    for i, failure in enumerate(failures, 1):
        if len(failures) > 1:
            print(f"\n{'#' * 80}")
            print(f"# Failure {i} of {len(failures)}")
            print(f"{'#' * 80}\n")
        analyze_failure(failure)
        
        # Optionally check checkpoint file for retry attempts
        if check_checkpoint:
            job_id = failures_file.stem.replace("failures_", "").replace("failures", "")
            check_checkpoint_file(job_id, failure.get('key', ''), failure.get('_idx'))
    
    # Summary
    print(f"\n{'=' * 80}")
    print("Summary:")
    parse_errors = sum(1 for f in failures if "parse_error" in f)
    fatal_errors = sum(1 for f in failures if "error" in f and "parse_error" not in f)
    with_raw = sum(1 for f in failures if f.get("_raw_output") or f.get("result"))
    
    print(f"  Total failures: {len(failures)}")
    print(f"  Parse errors: {parse_errors}")
    print(f"  Fatal errors: {fatal_errors}")
    print(f"  With raw output: {with_raw}")
    print(f"  Without raw output: {len(failures) - with_raw}")


if __name__ == "__main__":
    main()

