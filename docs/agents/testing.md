# Test Writing and Review

Before writing or reviewing Python tests, use the `write-python-test` skill.

If that skill is unavailable, raise the issue immediately and do not continue
with test writing or review.

Use 2D image-shaped data for model tests and examples; never use 1D or flat
inputs. Run local code validation with `bash scripts/validate_ci.sh` or focused
tests with `uv run python -m pytest`. GitHub Actions builds Sphinx docs.
