.PHONY: install lint format typecheck test check clean

# Use virtual environment binaries
VENV := .venv/bin

# Install dependencies
install:
	uv pip install -e ".[dev]"

# Lint code (check only)
lint:
	$(VENV)/ruff check agents/ tests/

# Format and auto-fix
format:
	$(VENV)/ruff check agents/ tests/ --fix
	$(VENV)/ruff format agents/ tests/

# Type checking
typecheck:
	$(VENV)/mypy agents/

# Run tests
test:
	$(VENV)/pytest tests/ -v

# Run all checks (lint + typecheck + test)
check: lint typecheck test

# Clean up cache files
clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
