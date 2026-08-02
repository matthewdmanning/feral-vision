# Test writing and review

Use this guide when writing or reviewing Python tests, test fixtures, or model
examples. Keep test data guidance here rather than in the general data guide.

Before writing or reviewing Python tests, use the `write-python-test` skill.
If that skill is unavailable, raise the issue immediately and do not continue
with test writing or review.

Always use 2D data when writing tests or examples of models. Never use 1D or
flat inputs. Dataset fixtures must follow the canonical `images/` and
`annotations/` layout when those directories are required by the code under
test.
