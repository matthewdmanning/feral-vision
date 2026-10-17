# Test writing and review

Use this guide when writing or reviewing Python tests, test fixtures, or model
examples. Keep test data guidance here rather than in the general data guide.

## Terraform test boundary

Terraform test files exist solely in [`feral-vision/terraform/tests/`](../../feral-vision/terraform/tests/).
Keep all `*.tftest.hcl` files, Terraform test fixtures, and Terraform test
support there. Do not place Terraform tests under `tests/`, `src/`, or a
Terraform module directory.

Python tests and fixtures remain under [`tests/`](../../tests/) and test Python
code under [`src/`](../../src/). The Python test tree and Terraform test tree
are completely separate: do not mix their files, fixtures, runners, or test
conventions.

Before writing or reviewing Python tests, search the official pytest
documentation for current best practices relevant to the change and apply
them. Use the official
[good integration practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html),
[fixture guidance](https://docs.pytest.org/en/stable/how-to/fixtures.html), and
[monkeypatch guidance](https://docs.pytest.org/en/stable/how-to/monkeypatch.html).

Use function-scoped fixtures by default, `tmp_path` for isolated filesystem
state, and `monkeypatch` or a context manager for changes that must be undone.
Pair state changes with teardown and keep fixtures focused. Parameterize
meaningful input variations instead of copying tests.

Check the packages under test for public testing assets and local integration
tools before building stand-ins. Use real library objects where practical.
When a mock is needed, use [unittest.mock autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing)
against the real API and patch where the dependency is looked up. Use
`side_effect` for injected failures and `torch.testing.assert_close` for tensor
comparisons. Keep tests focused on observable project behavior; avoid tests
that only reproduce implementation steps.

For training-module and source-adapter contract tests, mock model/data retrieval
through upstream APIs. Verify this module's calls, handoffs, and output contracts
without downloading external models or datasets or re-testing upstream retrieval.

Always use 2D data when writing tests or examples of models. Never use 1D or
flat inputs. Dataset fixtures must follow the canonical `images/` and
`annotations/` layout when those directories are required by the code under
test.
