#!/usr/bin/env bash
# Mirror the validation performed by the Dev and Training smoke GitHub workflows.
set -euo pipefail

export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

uv sync --group dev --group docs-sphinx
uvx ruff check . --output-format=github
uvx ruff format --check .
uv run mypy src
uv run python -m pytest -m "not gpu and not slow" -q --tb=short --cov=src --cov-report=xml
uv run sphinx-build -b html docs docs/_build -W
uv run python -c "import pytest, torch; torch.manual_seed(0); raise SystemExit(pytest.main(['tests/test_trainer.py', '-q', '--tb=short']))"
