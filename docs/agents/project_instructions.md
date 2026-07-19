# Project Instructions

## GitHub access

Follow the canonical [GitHub issue-tracker guidance](issue-tracker.md) for
GitHub Issues and pull-request work. Use the connected `@GitHub` app whenever
it supports the operation. For local GitHub CLI commands, load `.env.local`
without printing its contents and pass `GITHUB_PERSONAL_ACCESS_TOKEN` as
`GH_TOKEN`. Keep `.env.local` local; never commit it or copy its values into
documentation, issues, or logs.

## Git workspace hygiene

Do not leave stale Git worktrees or branches behind. Before finishing work,
remove worktrees and local branches created for the task once they are no longer
needed. Check their status first, and never remove an active, dirty, or
user-owned worktree or branch without explicit approval.

## Code placement

Keep reusable, project-agnostic code in `src/`. Put project-specific workflow,
deployment, and operational code in `scripts/`; do not turn project orchestration
into a reusable library API without a demonstrated cross-project use.
