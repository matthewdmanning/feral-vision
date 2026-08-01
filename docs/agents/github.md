# GitHub workflow

Use this guide for Git repository work, GitHub Issues or pull requests, and
publishing changes.

## Session prerequisites

At the beginning of a session involving repository or GitHub work, check that
`gh` is installed, `origin` is set, MCP servers respond, and any scripts needed
for the task are available. Report each missing or broken prerequisite with a
concise fix, then stop before work that depends on it.

Fetch `origin` before repository work. Fast-forward a clean local `main` from
`origin/main` before branching; do not pull, merge, rebase, or otherwise update
a dirty worktree or a feature branch without task-specific intent.

## GitHub access

Issues and PRDs for this repository live in GitHub Issues. Prefer the connected
GitHub app for supported issue and pull-request operations. Other agents and
operations not supported by the connector should use the `gh` CLI. Infer the
repository from `git remote -v`.

For CLI work, authenticate `gh` from the local `.env.local` token without
printing or committing secret values, then verify with `gh auth status`.
`GITHUB_PERSONAL_ACCESS_TOKEN` in this checkout's `.env.local` was validated
on 2026-07-21 at 12:00 noon. If `gh` reports an invalid token, repair its saved
credential from that local token before pursuing device authentication or
requesting a replacement token.

### Issue operations

- Create, read, list, comment on, label, and close issues through the connected
  GitHub app when available.
- With `gh`, use `gh issue create`, `gh issue view <number> --comments`,
  `gh issue list`, `gh issue comment`, `gh issue edit`, and `gh issue close`.
- Preserve full issue bodies, comments, and labels when gathering ticket
  context.
- GitHub shares one number space across issues and pull requests; resolve
  ambiguous references before acting.

### Pull-request operations

Never push directly to `main`; publish changes through a pull request. Create
commits with `uv run cz commit`; the Dev workflow validates Conventional Commit
messages on non-`main` branches.

#### Triage boundary

PRs are not a request surface.

Before opening or updating a pull request, fetch `origin/main` and integrate it
into the feature branch locally. Resolve any clashes locally and run the
relevant verification before publishing; do not leave conflict resolution to
GitHub.

When writing a pull-request description, use
[the repository template](../../.github/PULL_REQUEST_TEMPLATE.md) and include
only sections relevant to the change.

## Workspace hygiene

Before finishing work, remove worktrees and local branches created for the task
when they are no longer needed. Never remove an active, dirty, or user-owned
worktree or branch without explicit approval.

## Skill mappings

- "Publish to the issue tracker" means create a GitHub issue.
- "Fetch the relevant ticket" means fetch the issue body, labels, and comments.
- Prefer structured connector operations in Codex; use `gh` when connector
  coverage is insufficient.

## Wayfinding operations

- A map is an issue labeled `wayfinder:map`.
- Child tickets use GitHub sub-issues where available, falling back to a task
  list and `Part of #<map>`.
- Child labels use `wayfinder:<type>`: `research`, `prototype`, `grilling`, or
  `task`.
- Use native issue dependencies where available; otherwise add
  `Blocked by: #<number>` to the child body.
- The frontier is the first unassigned open child without open blockers.
- Claim a ticket by assigning it to the driving developer.
- Resolve it by commenting with the answer, closing it, and adding a short
  linked decision to the map.
