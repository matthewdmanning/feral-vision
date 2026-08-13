# Test writing and review

Use this guide when writing or reviewing Python tests, test fixtures, or model
examples. Keep test data guidance here rather than in the general data guide.

## Terraform test boundary

Terraform test files exist solely in [`terraform/tests/`](../../terraform/tests/).
Keep all `*.tftest.hcl` files, Terraform test fixtures, and Terraform test
support there. Do not place Terraform tests under `tests/`, `src/`, or a
Terraform module directory.

Python tests and fixtures remain under [`tests/`](../../tests/) and test Python
code under [`src/`](../../src/). The Python test tree and Terraform test tree
are completely separate: do not mix their files, fixtures, runners, or test
contracts.

Before writing or reviewing Python tests, use the `write-python-test` skill.
If that skill is unavailable, raise the issue immediately and do not continue
with test writing or review.

Always use 2D data when writing tests or examples of models. Never use 1D or
flat inputs. Dataset fixtures must follow the canonical `images/` and
`annotations/` layout when those directories are required by the code under
test.
