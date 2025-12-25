"""Post-processor for parsing LLM output into structured data."""

import json
import re
from typing import Any


class PostProcessor:
    """Post-processor for extracting and parsing structured data from LLM output."""

    @staticmethod
    def extract_json_from_markdown(text: str) -> dict[str, Any] | None:
        """
        Extract JSON from markdown code blocks.

        Handles formats like:
        - ```json\n{...}\n```
        - ```\n{...}\n```
        - Plain JSON: {...}

        Args:
            text: Text that may contain JSON in markdown code blocks.

        Returns:
            Parsed JSON dictionary, or None if extraction fails.
        """
        if not text:
            return None

        # Try to find JSON in markdown code blocks
        # Pattern matches: ```json\n...\n``` or ```\n...\n```
        markdown_pattern = r"```(?:json)?\s*\n(.*?)\n```"
        match = re.search(markdown_pattern, text, re.DOTALL)

        if match:
            json_str = match.group(1).strip()
        else:
            # Try to find JSON object directly (starts with { and ends with })
            json_pattern = r"\{.*\}"
            json_match = re.search(json_pattern, text, re.DOTALL)
            json_str = json_match.group(0) if json_match else text.strip()

        try:
            result: dict[str, Any] = json.loads(json_str)
            return result
        except (json.JSONDecodeError, ValueError):
            return None

    @staticmethod
    def process_result(
        result: dict[str, Any], merge: bool = True, include_raw: bool = False
    ) -> dict[str, Any]:
        """
        Process a result dictionary by extracting JSON from the 'result' field.

        Args:
            result: Result dictionary with a 'result' field containing LLM output.
            merge: Whether to merge parsed JSON fields into the root dictionary.
                   If False, parsed JSON is added to 'parsed' field.
            include_raw: Whether to include the original 'result' field in output.

        Returns:
            Processed result dictionary.
        """
        if "result" not in result:
            return result

        raw_result = result["result"]
        parsed_json = PostProcessor.extract_json_from_markdown(raw_result)

        # Create new dictionary
        processed = {**result}

        if parsed_json is not None:
            if merge:
                # Merge parsed fields into root
                processed.update(parsed_json)
            else:
                # Add to parsed field
                processed["parsed"] = parsed_json
        else:
            # If parsing failed, add error info
            processed["parse_error"] = "Failed to extract JSON from LLM output"
            # Always keep raw result when parsing fails for debugging
            # Store it in a separate field so it doesn't interfere with output
            processed["_raw_output"] = raw_result

        # Remove raw result if not requested (but keep _raw_output for parse errors)
        if not include_raw and "result" in processed:
            del processed["result"]

        return processed

    @staticmethod
    def process_results(
        results: list[dict[str, Any]], merge: bool = True, include_raw: bool = False
    ) -> list[dict[str, Any]]:
        """
        Process a list of result dictionaries.

        Args:
            results: List of result dictionaries.
            merge: Whether to merge parsed JSON fields into the root.
            include_raw: Whether to include raw LLM output.

        Returns:
            List of processed results.
        """
        return [
            PostProcessor.process_result(result, merge=merge, include_raw=include_raw)
            for result in results
        ]
