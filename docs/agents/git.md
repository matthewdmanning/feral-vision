# Git and GitHub workflow

Use this guide for Git repository work, GitHub Issues or pull requests, and
publishing changes.

## Session prerequisites

At the beginning of a session involving repository or GitHub work, check that
`gh` is installed, `origin` is set, MCP servers respond, and any scripts needed
for the task are available. Report each missing or broken prerequisite with a
concise fix, then stop before work that depends on it.

## GitHub access

Follow the canonical [issue-tracker guidance](issue-tracker.md) for GitHub
Issues and pull-request work. Prefer the connected GitHub app when it supports
the operation. For CLI work, authenticate `gh` from the local `.env.local`
token without printing or committing secret values, then verify with
`gh auth status`.

`GITHUB_PERSONAL_ACCESS_TOKEN` in this checkout's `.env.local` was validated
on 2026-07-21 at 12:00 noon. If `gh` reports an invalid token, repair its saved
credential from that local token before pursuing device authentication or
requesting a replacement token.

## Workspace hygiene

Never push directly to `main`; publish changes through a pull request. Create
commits with `uv run cz commit`; the Dev workflow validates Conventional Commit
messages on non-`main` branches.

Before finishing work, remove worktrees and local branches created for the task
when they are no longer needed. Never remove an active, dirty, or user-owned
worktree or branch without explicit approval.

When writing a pull-request description, use
[the repository template](../../.github/PULL_REQUEST_TEMPLATE.md) and include
only sections relevant to the change.
