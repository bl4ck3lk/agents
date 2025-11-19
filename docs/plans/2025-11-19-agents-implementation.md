# Agents - LLM Batch Processing Tool Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that processes large datasets using LLMs with support for multiple formats (CSV, JSON, JSONL, text, SQLite), sequential/async processing, and robust error handling.

**Architecture:** Adapter pattern for multiple input formats, processing engine with two modes (sequential/async), OpenAI client wrapper, job manager for orchestration, Click-based CLI.

**Tech Stack:** Python 3.11+, OpenAI SDK, Click, Pydantic, Tenacity, Rich, uv, ruff, mypy, pytest

---

## Phase 1: Project Setup

### Task 1: Initialize Python Project with uv

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `README.md`
- Create: `.gitignore`
- Create: `.env.example`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "agents"
version = "0.1.0"
description = "LLM batch processing CLI tool"
authors = [{name = "Your Name", email = "you@example.com"}]
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.50.0",
    "click>=8.1.7",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "tenacity>=9.0.0",
    "rich>=13.9.0",
    "aiosqlite>=0.20.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "mypy>=1.13.0",
    "ruff>=0.7.0",
]

[project.scripts]
agents = "agents.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create .python-version**

```
3.11
```

**Step 3: Create README.md**

```markdown
# Agents

LLM batch processing CLI tool.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
agents process input.csv output.csv --prompt "Translate '{text}' to Spanish"
```

See `docs/plans/2025-11-19-agents-design.md` for full design.
```

**Step 4: Create .gitignore**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Environment
.env
.env.local

# Progress files
.progress.json
*_partial.*

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json
```

**Step 5: Create .env.example**

```bash
# OpenAI API Key
OPENAI_API_KEY=sk-...

# Optional: Custom API endpoint
# OPENAI_BASE_URL=https://api.openai.com/v1
```

**Step 6: Commit project setup**

```bash
git add pyproject.toml .python-version README.md .gitignore .env.example
git commit -m "feat: initialize project with uv and tooling"
```

---

### Task 2: Create Package Structure

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/core/__init__.py`
- Create: `agents/adapters/__init__.py`
- Create: `agents/utils/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create package directories and __init__ files**

```bash
mkdir -p agents/core agents/adapters agents/utils tests
touch agents/__init__.py agents/core/__init__.py agents/adapters/__init__.py agents/utils/__init__.py tests/__init__.py
```

**Step 2: Add version to agents/__init__.py**

```python
"""Agents - LLM batch processing CLI tool."""

__version__ = "0.1.0"
```

**Step 3: Install project in dev mode**

Run: `uv pip install -e ".[dev]"`
Expected: Package installed successfully

**Step 4: Verify installation**

Run: `python -c "import agents; print(agents.__version__)"`
Expected: `0.1.0`

**Step 5: Commit package structure**

```bash
git add agents/ tests/
git commit -m "feat: create package structure"
```

---

## Phase 2: Base Adapter Interface

### Task 3: Define DataAdapter ABC

**Files:**
- Create: `agents/adapters/base.py`
- Create: `tests/test_adapters.py`

**Step 1: Write test for adapter interface**

File: `tests/test_adapters.py`

```python
"""Tests for data adapters."""

from typing import Iterator

import pytest

from agents.adapters.base import DataAdapter


class MockAdapter(DataAdapter):
    """Mock adapter for testing."""

    def __init__(self, units: list[dict[str, str]]) -> None:
        self._units = units
        self.results: list[dict[str, str]] = []

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read mock data units."""
        yield from self._units

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Store results."""
        self.results = results

    def get_schema(self) -> dict[str, str]:
        """Get schema."""
        return {"type": "mock"}


def test_adapter_interface() -> None:
    """Test adapter implements required interface."""
    units = [{"id": "1", "text": "hello"}, {"id": "2", "text": "world"}]
    adapter = MockAdapter(units)

    # Test read_units
    read_units = list(adapter.read_units())
    assert read_units == units

    # Test write_results
    results = [{"id": "1", "result": "hola"}, {"id": "2", "result": "mundo"}]
    adapter.write_results(results)
    assert adapter.results == results

    # Test get_schema
    schema = adapter.get_schema()
    assert schema == {"type": "mock"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py::test_adapter_interface -v`
Expected: FAIL with "No module named 'agents.adapters.base'"

**Step 3: Implement DataAdapter ABC**

File: `agents/adapters/base.py`

```python
"""Base adapter interface for data sources."""

from abc import ABC, abstractmethod
from typing import Iterator


class DataAdapter(ABC):
    """Abstract base class for data adapters."""

    @abstractmethod
    def read_units(self) -> Iterator[dict[str, str]]:
        """
        Read data units from source.

        Yields:
            Data units as dictionaries.
        """
        pass

    @abstractmethod
    def write_results(self, results: list[dict[str, str]]) -> None:
        """
        Write processed results to output.

        Args:
            results: List of result dictionaries.
        """
        pass

    @abstractmethod
    def get_schema(self) -> dict[str, str]:
        """
        Get schema information about the data source.

        Returns:
            Schema metadata as dictionary.
        """
        pass
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_adapters.py::test_adapter_interface -v`
Expected: PASS

**Step 5: Commit base adapter**

```bash
git add agents/adapters/base.py tests/test_adapters.py
git commit -m "feat: add DataAdapter base interface"
```

---

## Phase 3: CSV Adapter

### Task 4: Implement CSV Adapter

**Files:**
- Create: `agents/adapters/csv_adapter.py`
- Modify: `tests/test_adapters.py`
- Create: `tests/fixtures/sample.csv`

**Step 1: Write test for CSV adapter**

File: `tests/test_adapters.py` (append to file)

```python
import csv
from pathlib import Path

from agents.adapters.csv_adapter import CSVAdapter


def test_csv_adapter_read(tmp_path: Path) -> None:
    """Test CSV adapter reads data correctly."""
    # Create sample CSV
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,text\n1,hello\n2,world\n")

    adapter = CSVAdapter(str(csv_file), str(tmp_path / "output.csv"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": "1", "text": "hello"}
    assert units[1] == {"id": "2", "text": "world"}


def test_csv_adapter_write(tmp_path: Path) -> None:
    """Test CSV adapter writes results correctly."""
    input_file = tmp_path / "input.csv"
    output_file = tmp_path / "output.csv"
    input_file.write_text("id,text\n1,hello\n2,world\n")

    adapter = CSVAdapter(str(input_file), str(output_file))
    results = [
        {"id": "1", "text": "hello", "result": "hola"},
        {"id": "2", "text": "world", "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output
    with open(output_file) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0] == {"id": "1", "text": "hello", "result": "hola"}
    assert rows[1] == {"id": "2", "text": "world", "result": "mundo"}


def test_csv_adapter_get_schema(tmp_path: Path) -> None:
    """Test CSV adapter returns schema."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("id,text,category\n1,hello,greeting\n")

    adapter = CSVAdapter(str(csv_file), str(tmp_path / "output.csv"))
    schema = adapter.get_schema()

    assert schema["columns"] == ["id", "text", "category"]
    assert schema["type"] == "csv"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py::test_csv_adapter_read -v`
Expected: FAIL with "No module named 'agents.adapters.csv_adapter'"

**Step 3: Implement CSV adapter**

File: `agents/adapters/csv_adapter.py`

```python
"""CSV data adapter."""

import csv
from pathlib import Path
from typing import Iterator

from agents.adapters.base import DataAdapter


class CSVAdapter(DataAdapter):
    """Adapter for CSV files."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize CSV adapter.

        Args:
            input_path: Path to input CSV file.
            output_path: Path to output CSV file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self._columns: list[str] = []

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read CSV rows as data units."""
        with open(self.input_path, newline="") as f:
            reader = csv.DictReader(f)
            self._columns = reader.fieldnames or []
            for row in reader:
                yield dict(row)

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Write results to CSV file."""
        if not results:
            return

        # Get all unique keys from results
        fieldnames = list(results[0].keys())

        with open(self.output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    def get_schema(self) -> dict[str, str]:
        """Get CSV schema information."""
        # Read columns if not already loaded
        if not self._columns:
            with open(self.input_path, newline="") as f:
                reader = csv.DictReader(f)
                self._columns = reader.fieldnames or []

        return {"type": "csv", "columns": self._columns}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_adapters.py -k csv_adapter -v`
Expected: All CSV adapter tests PASS

**Step 5: Commit CSV adapter**

```bash
git add agents/adapters/csv_adapter.py tests/test_adapters.py
git commit -m "feat: add CSV adapter"
```

---

## Phase 4: JSONL Adapter

### Task 5: Implement JSONL Adapter

**Files:**
- Create: `agents/adapters/jsonl_adapter.py`
- Modify: `tests/test_adapters.py`

**Step 1: Write test for JSONL adapter**

File: `tests/test_adapters.py` (append)

```python
import json

from agents.adapters.jsonl_adapter import JSONLAdapter


def test_jsonl_adapter_read(tmp_path: Path) -> None:
    """Test JSONL adapter reads data correctly."""
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text('{"id": "1", "text": "hello"}\n{"id": "2", "text": "world"}\n')

    adapter = JSONLAdapter(str(jsonl_file), str(tmp_path / "output.jsonl"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": "1", "text": "hello"}
    assert units[1] == {"id": "2", "text": "world"}


def test_jsonl_adapter_write(tmp_path: Path) -> None:
    """Test JSONL adapter writes results correctly."""
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.jsonl"
    input_file.write_text('{"id": "1"}\n{"id": "2"}\n')

    adapter = JSONLAdapter(str(input_file), str(output_file))
    results = [
        {"id": "1", "result": "hola"},
        {"id": "2", "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"id": "1", "result": "hola"}
    assert json.loads(lines[1]) == {"id": "2", "result": "mundo"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py::test_jsonl_adapter_read -v`
Expected: FAIL with "No module named 'agents.adapters.jsonl_adapter'"

**Step 3: Implement JSONL adapter**

File: `agents/adapters/jsonl_adapter.py`

```python
"""JSONL (JSON Lines) data adapter."""

import json
from pathlib import Path
from typing import Iterator

from agents.adapters.base import DataAdapter


class JSONLAdapter(DataAdapter):
    """Adapter for JSONL (JSON Lines) files."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize JSONL adapter.

        Args:
            input_path: Path to input JSONL file.
            output_path: Path to output JSONL file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read JSONL lines as data units."""
        with open(self.input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Write results to JSONL file."""
        with open(self.output_path, "w") as f:
            for result in results:
                f.write(json.dumps(result) + "\n")

    def get_schema(self) -> dict[str, str]:
        """Get JSONL schema information."""
        return {"type": "jsonl"}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_adapters.py -k jsonl_adapter -v`
Expected: All JSONL adapter tests PASS

**Step 5: Commit JSONL adapter**

```bash
git add agents/adapters/jsonl_adapter.py tests/test_adapters.py
git commit -m "feat: add JSONL adapter"
```

---

## Phase 5: Text Adapter

### Task 6: Implement Text Adapter

**Files:**
- Create: `agents/adapters/text_adapter.py`
- Modify: `tests/test_adapters.py`

**Step 1: Write test for text adapter**

File: `tests/test_adapters.py` (append)

```python
from agents.adapters.text_adapter import TextAdapter


def test_text_adapter_read(tmp_path: Path) -> None:
    """Test text adapter reads lines correctly."""
    text_file = tmp_path / "test.txt"
    text_file.write_text("hello\nworld\n")

    adapter = TextAdapter(str(text_file), str(tmp_path / "output.txt"))
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"line_number": 1, "content": "hello"}
    assert units[1] == {"line_number": 2, "content": "world"}


def test_text_adapter_write(tmp_path: Path) -> None:
    """Test text adapter writes results correctly."""
    input_file = tmp_path / "input.txt"
    output_file = tmp_path / "output.txt"
    input_file.write_text("hello\nworld\n")

    adapter = TextAdapter(str(input_file), str(output_file))
    results = [
        {"line_number": 1, "content": "hello", "result": "hola"},
        {"line_number": 2, "content": "world", "result": "mundo"},
    ]

    adapter.write_results(results)

    # Verify output - should write just the result field
    lines = output_file.read_text().strip().split("\n")
    assert len(lines) == 2
    assert lines[0] == "hola"
    assert lines[1] == "mundo"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py::test_text_adapter_read -v`
Expected: FAIL with "No module named 'agents.adapters.text_adapter'"

**Step 3: Implement text adapter**

File: `agents/adapters/text_adapter.py`

```python
"""Text file adapter."""

from pathlib import Path
from typing import Iterator

from agents.adapters.base import DataAdapter


class TextAdapter(DataAdapter):
    """Adapter for plain text files (line-by-line)."""

    def __init__(self, input_path: str, output_path: str) -> None:
        """
        Initialize text adapter.

        Args:
            input_path: Path to input text file.
            output_path: Path to output text file.
        """
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read text lines as data units."""
        with open(self.input_path) as f:
            for line_number, line in enumerate(f, start=1):
                yield {"line_number": line_number, "content": line.rstrip("\n")}

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Write results to text file."""
        with open(self.output_path, "w") as f:
            for result in results:
                # Write the 'result' field if it exists, otherwise write content
                output_line = result.get("result", result.get("content", ""))
                f.write(output_line + "\n")

    def get_schema(self) -> dict[str, str]:
        """Get text file schema information."""
        return {"type": "text"}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_adapters.py -k text_adapter -v`
Expected: All text adapter tests PASS

**Step 5: Commit text adapter**

```bash
git add agents/adapters/text_adapter.py tests/test_adapters.py
git commit -m "feat: add text adapter"
```

---

## Phase 6: LLM Client Wrapper

### Task 7: Implement LLM Client

**Files:**
- Create: `agents/core/llm_client.py`
- Create: `tests/test_llm_client.py`

**Step 1: Write test for LLM client**

File: `tests/test_llm_client.py`

```python
"""Tests for LLM client."""

from unittest.mock import Mock, patch

import pytest
from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from agents.core.llm_client import LLMClient


@pytest.fixture
def mock_openai_client() -> Mock:
    """Mock OpenAI client."""
    client = Mock(spec=OpenAI)
    return client


def test_llm_client_initialization() -> None:
    """Test LLM client initializes correctly."""
    client = LLMClient(api_key="test-key", model="gpt-4o-mini")
    assert client.model == "gpt-4o-mini"


def test_llm_client_completion(mock_openai_client: Mock) -> None:
    """Test LLM client generates completions."""
    # Mock response
    mock_response = ChatCompletion(
        id="test",
        model="gpt-4o-mini",
        object="chat.completion",
        created=1234567890,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="Hello!"),
                finish_reason="stop",
            )
        ],
    )
    mock_openai_client.chat.completions.create.return_value = mock_response

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="test-key", model="gpt-4o-mini")
        response = client.complete("Test prompt")

    assert response == "Hello!"
    mock_openai_client.chat.completions.create.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py::test_llm_client_initialization -v`
Expected: FAIL with "No module named 'agents.core.llm_client'"

**Step 3: Implement LLM client**

File: `agents/core/llm_client.py`

```python
"""LLM client wrapper for OpenAI API."""

from typing import Any

from openai import OpenAI


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            api_key: API key for authentication.
            model: Model name to use.
            base_url: Optional base URL for API endpoint.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        return response.choices[0].message.content or ""
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm_client.py -v`
Expected: All LLM client tests PASS

**Step 5: Commit LLM client**

```bash
git add agents/core/llm_client.py tests/test_llm_client.py
git commit -m "feat: add LLM client wrapper"
```

---

## Phase 7: Prompt Templating

### Task 8: Implement Prompt Template

**Files:**
- Create: `agents/core/prompt.py`
- Create: `tests/test_prompt.py`

**Step 1: Write test for prompt template**

File: `tests/test_prompt.py`

```python
"""Tests for prompt templating."""

import pytest

from agents.core.prompt import PromptTemplate


def test_prompt_template_simple() -> None:
    """Test simple prompt template rendering."""
    template = PromptTemplate("Translate '{word}' to Spanish")
    result = template.render({"word": "hello"})
    assert result == "Translate 'hello' to Spanish"


def test_prompt_template_multiple_fields() -> None:
    """Test template with multiple fields."""
    template = PromptTemplate("Translate '{word}' from {lang_from} to {lang_to}")
    result = template.render({"word": "hello", "lang_from": "English", "lang_to": "Spanish"})
    assert result == "Translate 'hello' from English to Spanish"


def test_prompt_template_missing_field() -> None:
    """Test template with missing field raises error."""
    template = PromptTemplate("Translate '{word}' to Spanish")
    with pytest.raises(KeyError):
        template.render({"text": "hello"})


def test_prompt_template_get_fields() -> None:
    """Test extracting field names from template."""
    template = PromptTemplate("Translate '{word}' from {lang_from} to {lang_to}")
    fields = template.get_fields()
    assert fields == ["word", "lang_from", "lang_to"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompt.py::test_prompt_template_simple -v`
Expected: FAIL with "No module named 'agents.core.prompt'"

**Step 3: Implement prompt template**

File: `agents/core/prompt.py`

```python
"""Prompt template for LLM requests."""

import re
from string import Formatter


class PromptTemplate:
    """Template for rendering prompts with data."""

    def __init__(self, template: str) -> None:
        """
        Initialize prompt template.

        Args:
            template: Template string with {field} placeholders.
        """
        self.template = template
        self._formatter = Formatter()

    def render(self, data: dict[str, str]) -> str:
        """
        Render template with data.

        Args:
            data: Dictionary of field values.

        Returns:
            Rendered prompt string.

        Raises:
            KeyError: If required field is missing from data.
        """
        return self.template.format(**data)

    def get_fields(self) -> list[str]:
        """
        Extract field names from template.

        Returns:
            List of field names used in template.
        """
        return [
            field_name
            for _, field_name, _, _ in self._formatter.parse(self.template)
            if field_name is not None
        ]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_prompt.py -v`
Expected: All prompt template tests PASS

**Step 5: Commit prompt template**

```bash
git add agents/core/prompt.py tests/test_prompt.py
git commit -m "feat: add prompt template"
```

---

## Phase 8: Sequential Processing Engine

### Task 9: Implement Sequential Processing Engine

**Files:**
- Create: `agents/core/engine.py`
- Create: `tests/test_engine.py`

**Step 1: Write test for sequential engine**

File: `tests/test_engine.py`

```python
"""Tests for processing engine."""

from unittest.mock import Mock

import pytest

from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate


@pytest.fixture
def mock_llm_client() -> Mock:
    """Mock LLM client."""
    client = Mock(spec=LLMClient)
    client.complete.side_effect = lambda prompt: f"Result: {prompt}"
    return client


def test_sequential_processing(mock_llm_client: Mock) -> None:
    """Test sequential processing mode."""
    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL)

    units = [{"text": "hello"}, {"text": "world"}]
    results = list(engine.process(units))

    assert len(results) == 2
    assert results[0] == {"text": "hello", "result": "Result: Process: hello"}
    assert results[1] == {"text": "world", "result": "Result: Process: world"}
    assert mock_llm_client.complete.call_count == 2


def test_processing_with_error_handling(mock_llm_client: Mock) -> None:
    """Test processing handles errors gracefully."""
    mock_llm_client.complete.side_effect = [
        "Success",
        Exception("API error"),
        "Success again",
    ]

    template = PromptTemplate("Process: {text}")
    engine = ProcessingEngine(mock_llm_client, template, mode=ProcessingMode.SEQUENTIAL)

    units = [{"text": "one"}, {"text": "two"}, {"text": "three"}]
    results = list(engine.process(units))

    assert len(results) == 3
    assert results[0] == {"text": "one", "result": "Success"}
    assert "error" in results[1]
    assert results[2] == {"text": "three", "result": "Success again"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py::test_sequential_processing -v`
Expected: FAIL with "No module named 'agents.core.engine'"

**Step 3: Implement sequential processing engine**

File: `agents/core/engine.py`

```python
"""Processing engine for batch LLM operations."""

from enum import Enum
from typing import Any, Iterator

from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate


class ProcessingMode(str, Enum):
    """Processing mode for engine."""

    SEQUENTIAL = "sequential"
    ASYNC = "async"


class ProcessingEngine:
    """Engine for processing data units with LLM."""

    def __init__(
        self,
        llm_client: LLMClient,
        prompt_template: PromptTemplate,
        mode: ProcessingMode = ProcessingMode.SEQUENTIAL,
        batch_size: int = 10,
    ) -> None:
        """
        Initialize processing engine.

        Args:
            llm_client: LLM client for API calls.
            prompt_template: Template for rendering prompts.
            mode: Processing mode (sequential or async).
            batch_size: Batch size for async mode.
        """
        self.llm_client = llm_client
        self.prompt_template = prompt_template
        self.mode = mode
        self.batch_size = batch_size

    def process(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """
        Process data units with LLM.

        Args:
            units: List of data units to process.

        Yields:
            Processed results with original data + result field.
        """
        if self.mode == ProcessingMode.SEQUENTIAL:
            yield from self._process_sequential(units)
        else:
            raise NotImplementedError("Async mode not yet implemented")

    def _process_sequential(self, units: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
        """Process units sequentially."""
        for unit in units:
            try:
                prompt = self.prompt_template.render(unit)
                result = self.llm_client.complete(prompt)
                yield {**unit, "result": result}
            except Exception as e:
                yield {**unit, "error": str(e)}
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_engine.py -v`
Expected: All engine tests PASS

**Step 5: Commit processing engine**

```bash
git add agents/core/engine.py tests/test_engine.py
git commit -m "feat: add sequential processing engine"
```

---

## Phase 9: Basic CLI Interface

### Task 10: Implement Basic CLI

**Files:**
- Create: `agents/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write test for CLI**

File: `tests/test_cli.py`

```python
"""Tests for CLI interface."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from agents.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner."""
    return CliRunner()


def test_cli_help(runner: CliRunner) -> None:
    """Test CLI help message."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "agents" in result.output.lower()


def test_cli_version(runner: CliRunner) -> None:
    """Test CLI version command."""
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py::test_cli_help -v`
Expected: FAIL with "No module named 'agents.cli'"

**Step 3: Implement basic CLI**

File: `agents/cli.py`

```python
"""CLI interface for agents."""

import click

from agents import __version__


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agents - LLM batch processing CLI tool."""
    pass


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@click.option("--prompt", required=True, help="Prompt template with {field} placeholders")
@click.option("--model", default="gpt-4o-mini", help="LLM model to use")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
def process(
    input_file: str, output_file: str, prompt: str, model: str, api_key: str
) -> None:
    """Process INPUT_FILE and save results to OUTPUT_FILE."""
    click.echo(f"Processing {input_file} -> {output_file}")
    click.echo(f"Model: {model}")
    click.echo(f"Prompt: {prompt}")
    click.echo("Not yet implemented - coming soon!")


if __name__ == "__main__":
    cli()
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All CLI tests PASS

**Step 5: Verify CLI works from command line**

Run: `agents --version`
Expected: `agents, version 0.1.0`

Run: `agents --help`
Expected: Help text with commands

**Step 6: Commit basic CLI**

```bash
git add agents/cli.py tests/test_cli.py
git commit -m "feat: add basic CLI interface"
```

---

## Phase 10: Configuration System

### Task 11: Implement Configuration

**Files:**
- Create: `agents/utils/config.py`
- Create: `tests/test_config.py`
- Create: `docs/examples/translation.yaml`

**Step 1: Write test for config loading**

File: `tests/test_config.py`

```python
"""Tests for configuration."""

from pathlib import Path

import pytest
import yaml

from agents.utils.config import JobConfig, load_config


def test_load_config_from_yaml(tmp_path: Path) -> None:
    """Test loading config from YAML file."""
    config_file = tmp_path / "config.yaml"
    config_data = {
        "llm": {
            "model": "gpt-4o-mini",
            "temperature": 0.5,
            "max_tokens": 1000,
        },
        "processing": {
            "mode": "sequential",
            "max_retries": 5,
        },
        "prompt": "Translate {text} to Spanish",
        "output": {
            "format": "json",
        },
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    config = load_config(str(config_file))

    assert config.llm.model == "gpt-4o-mini"
    assert config.llm.temperature == 0.5
    assert config.processing.mode == "sequential"
    assert config.prompt == "Translate {text} to Spanish"


def test_config_defaults() -> None:
    """Test config with default values."""
    config = JobConfig(
        llm={"model": "gpt-4o-mini", "api_key": "test"},
        prompt="Test {field}",
    )

    assert config.llm.temperature == 0.7  # default
    assert config.processing.mode == "async"  # default
    assert config.processing.batch_size == 10  # default
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_load_config_from_yaml -v`
Expected: FAIL with "No module named 'agents.utils.config'"

**Step 3: Implement configuration system**

File: `agents/utils/config.py`

```python
"""Configuration management."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class LLMConfig(BaseModel):
    """LLM configuration."""

    provider: str = "openai"
    model: str = "gpt-4o-mini"
    base_url: str | None = None
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    temperature: float = 0.7
    max_tokens: int = 500


class ProcessingConfig(BaseModel):
    """Processing configuration."""

    mode: str = "async"
    batch_size: int = 10
    max_retries: int = 3
    retry_delay: float = 1.0


class OutputConfig(BaseModel):
    """Output configuration."""

    format: str = "json"
    merge_strategy: str = "extend"


class JobConfig(BaseModel):
    """Complete job configuration."""

    llm: LLMConfig
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    prompt: str


def load_config(path: str) -> JobConfig:
    """
    Load configuration from YAML file.

    Args:
        path: Path to config file.

    Returns:
        Loaded configuration.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    return JobConfig(**data)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All config tests PASS

**Step 5: Create example config**

File: `docs/examples/translation.yaml`

```yaml
# Example configuration for translation task

llm:
  provider: openai
  model: gpt-4o-mini
  api_key: ${OPENAI_API_KEY}
  temperature: 0.3
  max_tokens: 200

processing:
  mode: async
  batch_size: 10
  max_retries: 3

prompt: |
  Translate the following word to Spanish, French, and German.
  Word: {word}

  Return ONLY valid JSON in this format:
  {"es": "spanish", "fr": "french", "de": "german"}

output:
  format: json
  merge_strategy: extend
```

**Step 6: Commit configuration system**

```bash
git add agents/utils/config.py tests/test_config.py docs/examples/translation.yaml
git commit -m "feat: add configuration system with YAML support"
```

---

## Phase 11: Integration - Wire Everything Together

### Task 12: Implement Full Processing Pipeline

**Files:**
- Modify: `agents/cli.py`
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

File: `tests/test_integration.py`

```python
"""Integration tests."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from agents.cli import cli


@pytest.fixture
def sample_csv(tmp_path: Path) -> Path:
    """Create sample CSV file."""
    csv_file = tmp_path / "input.csv"
    csv_file.write_text("word\nhello\nworld\n")
    return csv_file


@pytest.fixture
def mock_openai_response() -> Mock:
    """Mock OpenAI response."""
    mock = Mock()
    mock.choices = [Mock(message=Mock(content='{"es": "hola"}'))]
    return mock


def test_process_csv_with_prompt(
    runner: CliRunner, sample_csv: Path, tmp_path: Path, mock_openai_response: Mock
) -> None:
    """Test processing CSV file with prompt."""
    output_file = tmp_path / "output.csv"

    with patch("agents.core.llm_client.OpenAI") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_openai_response

        result = runner.invoke(
            cli,
            [
                "process",
                str(sample_csv),
                str(output_file),
                "--prompt",
                "Translate {word}",
                "--api-key",
                "test-key",
            ],
        )

    assert result.exit_code == 0
    assert output_file.exists()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_integration.py::test_process_csv_with_prompt -v`
Expected: FAIL - CLI not yet wired up

**Step 3: Wire up CLI with processing pipeline**

File: `agents/cli.py` (replace existing `process` command)

```python
"""CLI interface for agents."""

import sys
from pathlib import Path

import click

from agents import __version__
from agents.adapters.csv_adapter import CSVAdapter
from agents.adapters.jsonl_adapter import JSONLAdapter
from agents.adapters.text_adapter import TextAdapter
from agents.core.engine import ProcessingEngine, ProcessingMode
from agents.core.llm_client import LLMClient
from agents.core.prompt import PromptTemplate


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """Agents - LLM batch processing CLI tool."""
    pass


def get_adapter(input_path: str, output_path: str):
    """Get appropriate adapter based on file extension."""
    ext = Path(input_path).suffix.lower()

    if ext == ".csv":
        return CSVAdapter(input_path, output_path)
    elif ext == ".jsonl":
        return JSONLAdapter(input_path, output_path)
    elif ext == ".txt":
        return TextAdapter(input_path, output_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.argument("output_file", type=click.Path())
@click.option("--prompt", required=True, help="Prompt template with {field} placeholders")
@click.option("--model", default="gpt-4o-mini", help="LLM model to use")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key")
@click.option(
    "--mode",
    type=click.Choice(["sequential", "async"]),
    default="sequential",
    help="Processing mode",
)
@click.option("--batch-size", default=10, help="Batch size for async mode")
def process(
    input_file: str,
    output_file: str,
    prompt: str,
    model: str,
    api_key: str | None,
    mode: str,
    batch_size: int,
) -> None:
    """Process INPUT_FILE and save results to OUTPUT_FILE."""
    if not api_key:
        click.echo("Error: API key required (set OPENAI_API_KEY or use --api-key)", err=True)
        sys.exit(1)

    try:
        # Initialize components
        adapter = get_adapter(input_file, output_file)
        llm_client = LLMClient(api_key=api_key, model=model)
        prompt_template = PromptTemplate(prompt)

        processing_mode = ProcessingMode.SEQUENTIAL if mode == "sequential" else ProcessingMode.ASYNC
        engine = ProcessingEngine(
            llm_client, prompt_template, mode=processing_mode, batch_size=batch_size
        )

        # Process data
        click.echo(f"Processing {input_file} -> {output_file}")
        units = list(adapter.read_units())
        click.echo(f"Found {len(units)} units to process")

        results = list(engine.process(units))
        adapter.write_results(results)

        click.echo(f"✓ Successfully processed {len(results)} units")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
```

**Step 4: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: Integration test PASS

**Step 5: Manual test with real file**

Create test file:
```bash
echo -e "word\nhello\nworld" > /tmp/test.csv
```

Run (with fake key to test error handling):
```bash
agents process /tmp/test.csv /tmp/output.csv --prompt "Test {word}" --api-key test
```
Expected: Error message about authentication (proves wiring works)

**Step 6: Commit integration**

```bash
git add agents/cli.py tests/test_integration.py
git commit -m "feat: wire up CLI with processing pipeline"
```

---

## Phase 12: Retry Logic with Tenacity

### Task 13: Add Retry Logic to LLM Client

**Files:**
- Modify: `agents/core/llm_client.py`
- Modify: `tests/test_llm_client.py`

**Step 1: Write test for retry logic**

File: `tests/test_llm_client.py` (append)

```python
from openai import APIError, RateLimitError


def test_llm_client_retries_on_rate_limit(mock_openai_client: Mock) -> None:
    """Test client retries on rate limit errors."""
    # First two calls fail, third succeeds
    mock_response = ChatCompletion(
        id="test",
        model="gpt-4o-mini",
        object="chat.completion",
        created=1234567890,
        choices=[
            Choice(
                index=0,
                message=ChatCompletionMessage(role="assistant", content="Success!"),
                finish_reason="stop",
            )
        ],
    )

    mock_openai_client.chat.completions.create.side_effect = [
        RateLimitError("Rate limit"),
        RateLimitError("Rate limit"),
        mock_response,
    ]

    with patch("agents.core.llm_client.OpenAI", return_value=mock_openai_client):
        client = LLMClient(api_key="test-key", model="gpt-4o-mini", max_retries=3)
        response = client.complete("Test")

    assert response == "Success!"
    assert mock_openai_client.chat.completions.create.call_count == 3
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py::test_llm_client_retries_on_rate_limit -v`
Expected: FAIL - no retry logic yet

**Step 3: Add retry logic with tenacity**

File: `agents/core/llm_client.py` (modify)

```python
"""LLM client wrapper for OpenAI API."""

from typing import Any

from openai import APIError, OpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        max_retries: int = 3,
    ) -> None:
        """
        Initialize LLM client.

        Args:
            api_key: API key for authentication.
            model: Model name to use.
            base_url: Optional base URL for API endpoint.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            max_retries: Maximum retry attempts for transient errors.
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _make_request(self, prompt: str, **kwargs: Any) -> str:
        """Make API request with retry logic."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        return response.choices[0].message.content or ""

    def complete(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate completion for prompt.

        Args:
            prompt: Input prompt.
            **kwargs: Additional arguments for API call.

        Returns:
            Generated text response.
        """
        return self._make_request(prompt, **kwargs)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_llm_client.py -v`
Expected: All tests PASS

**Step 5: Commit retry logic**

```bash
git add agents/core/llm_client.py tests/test_llm_client.py
git commit -m "feat: add retry logic with exponential backoff"
```

---

## Phase 13: Progress Tracking

### Task 14: Implement Progress Tracking

**Files:**
- Create: `agents/utils/progress.py`
- Create: `tests/test_progress.py`

**Step 1: Write test for progress tracker**

File: `tests/test_progress.py`

```python
"""Tests for progress tracking."""

from pathlib import Path

import pytest

from agents.utils.progress import ProgressTracker


def test_progress_tracker_initialization(tmp_path: Path) -> None:
    """Test progress tracker initializes correctly."""
    tracker = ProgressTracker(total=100, checkpoint_dir=str(tmp_path))
    assert tracker.total == 100
    assert tracker.processed == 0


def test_progress_tracker_update(tmp_path: Path) -> None:
    """Test progress tracker updates."""
    tracker = ProgressTracker(total=10, checkpoint_dir=str(tmp_path))

    tracker.update(1)
    assert tracker.processed == 1

    tracker.update(5)
    assert tracker.processed == 6


def test_progress_tracker_save_checkpoint(tmp_path: Path) -> None:
    """Test saving checkpoint."""
    tracker = ProgressTracker(total=100, checkpoint_dir=str(tmp_path), job_id="test-job")

    tracker.update(50)
    tracker.increment_failed()
    tracker.save_checkpoint()

    checkpoint_file = tmp_path / ".progress_test-job.json"
    assert checkpoint_file.exists()

    # Verify checkpoint data
    import json

    with open(checkpoint_file) as f:
        data = json.load(f)

    assert data["processed"] == 50
    assert data["total"] == 100
    assert data["failed"] == 1


def test_progress_tracker_load_checkpoint(tmp_path: Path) -> None:
    """Test loading checkpoint."""
    # Create checkpoint
    tracker1 = ProgressTracker(total=100, checkpoint_dir=str(tmp_path), job_id="test-job")
    tracker1.update(50)
    tracker1.save_checkpoint()

    # Load checkpoint
    tracker2 = ProgressTracker.load_checkpoint(str(tmp_path), "test-job")

    assert tracker2.processed == 50
    assert tracker2.total == 100
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_progress.py::test_progress_tracker_initialization -v`
Expected: FAIL with "No module named 'agents.utils.progress'"

**Step 3: Implement progress tracker**

File: `agents/utils/progress.py`

```python
"""Progress tracking and checkpointing."""

import json
from pathlib import Path
from typing import Any


class ProgressTracker:
    """Track processing progress and save checkpoints."""

    def __init__(
        self, total: int, checkpoint_dir: str, job_id: str = "default", checkpoint_interval: int = 100
    ) -> None:
        """
        Initialize progress tracker.

        Args:
            total: Total number of units to process.
            checkpoint_dir: Directory for checkpoint files.
            job_id: Unique job identifier.
            checkpoint_interval: Save checkpoint every N units.
        """
        self.total = total
        self.processed = 0
        self.failed = 0
        self.checkpoint_dir = Path(checkpoint_dir)
        self.job_id = job_id
        self.checkpoint_interval = checkpoint_interval

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def update(self, count: int = 1) -> None:
        """
        Update processed count.

        Args:
            count: Number of units processed.
        """
        self.processed += count

        if self.processed % self.checkpoint_interval == 0:
            self.save_checkpoint()

    def increment_failed(self) -> None:
        """Increment failed count."""
        self.failed += 1

    def save_checkpoint(self) -> None:
        """Save checkpoint to file."""
        checkpoint_file = self.checkpoint_dir / f".progress_{self.job_id}.json"
        data = {
            "processed": self.processed,
            "total": self.total,
            "failed": self.failed,
            "job_id": self.job_id,
        }

        with open(checkpoint_file, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_checkpoint(cls, checkpoint_dir: str, job_id: str) -> "ProgressTracker":
        """
        Load progress from checkpoint file.

        Args:
            checkpoint_dir: Directory containing checkpoint.
            job_id: Job identifier.

        Returns:
            Restored progress tracker.
        """
        checkpoint_file = Path(checkpoint_dir) / f".progress_{job_id}.json"

        with open(checkpoint_file) as f:
            data = json.load(f)

        tracker = cls(
            total=data["total"], checkpoint_dir=checkpoint_dir, job_id=data["job_id"]
        )
        tracker.processed = data["processed"]
        tracker.failed = data.get("failed", 0)

        return tracker

    def get_progress(self) -> dict[str, Any]:
        """Get current progress stats."""
        percentage = (self.processed / self.total * 100) if self.total > 0 else 0
        return {
            "processed": self.processed,
            "total": self.total,
            "failed": self.failed,
            "percentage": round(percentage, 1),
        }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_progress.py -v`
Expected: All progress tests PASS

**Step 5: Commit progress tracking**

```bash
git add agents/utils/progress.py tests/test_progress.py
git commit -m "feat: add progress tracking and checkpointing"
```

---

## Phase 14: Additional Example Configs

### Task 15: Create Example Configurations

**Files:**
- Create: `docs/examples/summarization.yaml`
- Create: `docs/examples/classification.yaml`
- Modify: `README.md`

**Step 1: Create summarization example**

File: `docs/examples/summarization.yaml`

```yaml
# Example: Summarize text content

llm:
  model: gpt-4o-mini
  temperature: 0.5
  max_tokens: 150

processing:
  mode: async
  batch_size: 5

prompt: |
  Summarize the following text in 1-2 sentences:

  {content}

  Summary:

output:
  format: text
```

**Step 2: Create classification example**

File: `docs/examples/classification.yaml`

```yaml
# Example: Classify text into categories

llm:
  model: gpt-4o-mini
  temperature: 0.2
  max_tokens: 50

processing:
  mode: async
  batch_size: 20

prompt: |
  Classify the following text into one of these categories: Technology, Business, Sports, Entertainment

  Text: {text}

  Category:

output:
  format: text
```

**Step 3: Update README with examples**

File: `README.md` (append)

```markdown

## Examples

### Translation

```bash
agents process words.csv translations.csv --config docs/examples/translation.yaml
```

### Summarization

```bash
agents process articles.txt summaries.txt --config docs/examples/summarization.yaml
```

### Classification

```bash
agents process posts.jsonl categories.jsonl --config docs/examples/classification.yaml
```

## Development

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy agents/

# Linting
ruff check agents/
```
```

**Step 4: Commit examples and documentation**

```bash
git add docs/examples/ README.md
git commit -m "docs: add example configurations and usage"
```

---

## Phase 15: Final Polish & Documentation

### Task 16: Add Type Checking and Linting Config

**Files:**
- Modify: `pyproject.toml`
- Create: `.ruff.toml`

**Step 1: Enhance ruff configuration**

File: `.ruff.toml`

```toml
# Ruff configuration
line-length = 100
target-version = "py311"

[lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "W",   # pycodestyle warnings
    "UP",  # pyupgrade
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "DTZ", # flake8-datetimez
    "SIM", # flake8-simplify
]

ignore = [
    "E501", # line too long (handled by formatter)
]

[format]
quote-style = "double"
indent-style = "space"
```

**Step 2: Run linting**

Run: `ruff check agents/`
Expected: No errors or fixable issues

Run: `ruff format agents/`
Expected: Files formatted

**Step 3: Run type checking**

Run: `mypy agents/`
Expected: No type errors (or minimal that can be annotated)

**Step 4: Commit tooling config**

```bash
git add .ruff.toml pyproject.toml
git commit -m "chore: enhance linting and type checking config"
```

---

### Task 17: Add SQLite Adapter (Bonus)

**Files:**
- Create: `agents/adapters/sqlite_adapter.py`
- Modify: `tests/test_adapters.py`

**Step 1: Write test for SQLite adapter**

File: `tests/test_adapters.py` (append)

```python
import sqlite3

from agents.adapters.sqlite_adapter import SQLiteAdapter


def test_sqlite_adapter_read(tmp_path: Path) -> None:
    """Test SQLite adapter reads data correctly."""
    db_file = tmp_path / "test.db"

    # Create test database
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE words (id INTEGER, word TEXT)")
    conn.execute("INSERT INTO words VALUES (1, 'hello'), (2, 'world')")
    conn.commit()
    conn.close()

    adapter = SQLiteAdapter(
        f"sqlite://{db_file}?query=SELECT * FROM words", str(tmp_path / "output.db")
    )
    units = list(adapter.read_units())

    assert len(units) == 2
    assert units[0] == {"id": "1", "word": "hello"}
    assert units[1] == {"id": "2", "word": "world"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_adapters.py::test_sqlite_adapter_read -v`
Expected: FAIL with "No module named 'agents.adapters.sqlite_adapter'"

**Step 3: Implement SQLite adapter**

File: `agents/adapters/sqlite_adapter.py`

```python
"""SQLite database adapter."""

import sqlite3
from pathlib import Path
from typing import Iterator
from urllib.parse import parse_qs, urlparse

from agents.adapters.base import DataAdapter


class SQLiteAdapter(DataAdapter):
    """Adapter for SQLite databases."""

    def __init__(self, input_uri: str, output_path: str) -> None:
        """
        Initialize SQLite adapter.

        Args:
            input_uri: SQLite URI with query (sqlite://path?query=SELECT...)
            output_path: Path to output file.
        """
        parsed = urlparse(input_uri)
        self.db_path = parsed.path
        query_params = parse_qs(parsed.query)
        self.query = query_params.get("query", ["SELECT * FROM data"])[0]
        self.output_path = Path(output_path)

    def read_units(self) -> Iterator[dict[str, str]]:
        """Read database rows as data units."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(self.query)

        for row in cursor:
            yield {key: str(row[key]) for key in row.keys()}

        conn.close()

    def write_results(self, results: list[dict[str, str]]) -> None:
        """Write results to SQLite database."""
        if not results:
            return

        # For simplicity, write to a new table
        conn = sqlite3.connect(self.output_path)

        # Create table from first result
        columns = list(results[0].keys())
        placeholders = ", ".join(["?" for _ in columns])
        create_sql = f"CREATE TABLE IF NOT EXISTS results ({', '.join(f'{col} TEXT' for col in columns)})"
        insert_sql = f"INSERT INTO results VALUES ({placeholders})"

        conn.execute(create_sql)

        for result in results:
            conn.execute(insert_sql, [result[col] for col in columns])

        conn.commit()
        conn.close()

    def get_schema(self) -> dict[str, str]:
        """Get SQLite schema information."""
        return {"type": "sqlite", "query": self.query}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_adapters.py::test_sqlite_adapter_read -v`
Expected: PASS

**Step 5: Commit SQLite adapter**

```bash
git add agents/adapters/sqlite_adapter.py tests/test_adapters.py
git commit -m "feat: add SQLite adapter"
```

---

## Summary

This plan provides a complete, test-driven implementation path for the agents tool. Each task:

1. Writes failing tests first (TDD)
2. Implements minimal code to pass
3. Commits immediately
4. Builds incrementally

**Key Skills to Reference:**
- @superpowers:test-driven-development - Used throughout
- @superpowers:verification-before-completion - Use before marking complete
- @superpowers:systematic-debugging - If issues arise

**Total estimated tasks:** 17
**Estimated time:** 3-4 hours for experienced developer

**Next Steps After Implementation:**
1. Run full test suite: `pytest -v --cov=agents`
2. Type check: `mypy agents/`
3. Lint: `ruff check agents/`
4. Manual testing with real LLM API
5. Update README with real-world examples
