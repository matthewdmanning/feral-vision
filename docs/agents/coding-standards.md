# Coding standards

Use this guide when changing project code or authored documentation. Keep
substantive project behavior documented with the implementation that changes
it, and route domain vocabulary, cloud operations, data formats, and
workflow-specific guidance to their canonical agent references.

## Documentation

Functions longer than three lines and class definitions must have docstrings.
All docstrings must be written using NumPy style.

The main agent must update the canonical project documentation in the same
change whenever code changes substantive project behavior. This includes
program flow, integrations or deployment paths, runtime/configuration behavior,
data or tracking formats, public interfaces, and operator workflows. A purely
internal refactor that preserves that behavior does not require documentation
changes. Do not defer this check to a later session or reviewer.

When a change affects a user-visible workflow, update the relevant document in
`docs/guide/` in the same change. If no guide changes are needed, record that
the guide-impact check was completed in the handoff.

Do not commit `docs/_build/` or run Sphinx as part of local validation:
GitHub Actions rebuilds documentation on documentation changes and deploys the
generated Pages artifact from `main`.

## Code quality

Before adding project code for a capability, check whether a library already in
use provides it. Use that library directly unless a project-specific boundary is
genuinely required.
