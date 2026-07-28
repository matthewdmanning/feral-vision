# Implementation

Use this guide for code or authored-documentation changes.

Functions longer than three lines and class definitions require NumPy-style
docstrings. Keep command-line interfaces in shell scripts, not Python.

Before adding a capability, use an existing project dependency unless a
project-specific boundary is genuinely required. Update canonical documentation
with any substantive contract change; update `docs/guide/` when the change is
user-visible. GitHub Actions, not local validation, builds Sphinx output.
