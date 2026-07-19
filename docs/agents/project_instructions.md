# Project Instructions

## GitHub access

Follow the canonical [GitHub issue-tracker guidance](issue-tracker.md) for
GitHub Issues and pull-request work. Use the connected `@GitHub` app whenever
it supports the operation. For local GitHub CLI commands, load `.env.local`
without printing its contents and pass `GITHUB_PERSONAL_ACCESS_TOKEN` as
`GH_TOKEN`. Keep `.env.local` local; never commit it or copy its values into
documentation, issues, or logs. If device authentication fails, authenticate
`gh` from the local `GH_ACCESS_TOKEN` with `gh auth login --with-token`, then
verify it with `gh auth status` before performing issue operations.

## Git workspace hygiene

Never push directly to `main`; publish changes through a pull request.
Create commits with `uv run cz commit`; the Dev workflow validates the
Conventional Commit messages on non-`main` branches.

Do not leave stale Git worktrees or branches behind. Before finishing work,
remove worktrees and local branches created for the task once they are no longer
needed. Check their status first, and never remove an active, dirty, or
user-owned worktree or branch without explicit approval.
