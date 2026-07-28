# Git and GitHub

Use this guide for repository work, issues, pull requests, or publishing.

Check `gh`, `origin`, MCP availability, and task scripts before dependent work.
Fetch `origin` first. Fast-forward a clean local `main` from `origin/main`
before branching; never update a dirty worktree or feature branch without
task-specific intent.

Prefer the connected GitHub app; use `gh` when it lacks coverage. Authenticate
the CLI from `.env.local` without exposing its token, then verify with `gh auth
status`. Never push directly to `main`; use Conventional Commit messages and a
pull request.

Before opening or updating a PR, integrate `origin/main` locally, resolve
clashes locally, and run relevant verification. Use the repository PR template.

Issues and PRDs live in GitHub Issues. Preserve issue bodies, comments, and
labels when gathering context. Resolve ambiguous issue/PR numbers before acting.
Create, read, list, comment on, label, or close issues through the GitHub app
when available, otherwise use `gh issue`.
