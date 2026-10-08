# Test Assessment Documentation

## Summary

Create one Markdown assessment per `tests/test_*.py` module under
`tests/assessments/`. The repository has 16 test modules, all with
module-level tests and no pytest test classes.

## Structure

Each assessment uses:

```markdown
# test_<module>.py

## Module-level tests

### test_<method>

Purpose: <concise description of the behavior verified>

Load-bearing: True | False

Occurrence probability: <0-5>

#### <fixture>
```

Use `## Module-level tests` as the synthetic parent. Add every test method as
`###`. Add method fixtures—including shared `conftest.py` and built-in pytest
fixtures—as `####`. Use `#### default` when a method has no fixtures.

Exclude `tests/conftest.py`, fixture assets, bytecode, and support files.

## Assessment criteria

For each test purpose:

- `Load-bearing: True` means the behavior is a production contract, safety
  boundary, data/model lineage guarantee, or failure that would materially
  invalidate a supported workflow.
- `Load-bearing: False` means the test mainly covers presentation, helper
  behavior, exploratory tooling, implementation detail, or a lower-impact
  convenience contract.
- `Occurrence probability` rates how likely the tested situation is to occur
  in supported operation:
  - `0`: effectively impossible or purely synthetic
  - `1`: exceptionally rare; comparable to guessing a private key
  - `2`: rare but plausible
  - `3`: approximately 1 in 100 relevant operations
  - `4`: recurring, but less than daily
  - `5`: occurs daily or more

Score the production scenario represented by the test, not how often pytest
executes it. Record a short rationale when the load-bearing or probability
judgment is non-obvious.

## Validation

- Confirm every `tests/test_*.py` has exactly one assessment file.
- Confirm every test method appears once.
- Confirm fixture headings match method parameters.
- Confirm every method has exactly one load-bearing judgment and one
  probability score from `0` through `5`.
- Run `git diff --check`.
- Leave existing test code, staged deletions, and stashes unchanged.
