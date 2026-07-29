#!/usr/bin/env bash
# Run local code validation. GitHub Actions builds documentation.
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

uv sync --group dev
uv run ruff check . --output-format=github
uv run ruff format --check .
uv run mypy src
uv run python -m pytest -m "not gpu and not slow" -q --tb=short --cov=src --cov-report=xml
uv run python -c "import pytest, torch; torch.manual_seed(0); raise SystemExit(pytest.main(['tests/test_trainer.py', '-q', '--tb=short']))"
