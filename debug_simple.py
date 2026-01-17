#!/usr/bin/env python3

"""Simple debug script to test LLM responses directly."""

import os

from openai import OpenAI

# Load API key from environment
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: OPENAI_API_KEY not set")
    exit(1)

client = OpenAI(api_key=api_key)

# Test prompt - simple version
prompt = """You are a translator. The key is "test.key". The English text is "Hello World". Provide the Spanish translation. Return ONLY this JSON: {"es": "Hola Mundo"}"""

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=100,
    )

    content = response.choices[0].message.content
    print("LLM Response:")
    print(repr(content))
    print("\nFormatted Response:")
    print(content)

    # Try to parse as JSON
    import json

    try:
        parsed = json.loads(content)
        print("\nParsed JSON:")
        print(parsed)
    except json.JSONDecodeError as e:
        print(f"\nJSON Parse Error: {e}")

except Exception as e:
    print(f"Error calling LLM: {e}")
