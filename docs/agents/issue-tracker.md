# Issue tracker: GitHub

Issues and PRDs for this repository live in GitHub Issues.

Codex should prefer its connected GitHub app for supported issue operations. Other agents and operations not supported by the connector should use the `gh` CLI. Infer the repository from `git remote -v`.

## Conventions

- Create, read, list, comment on, label, and close issues through the connected GitHub app when available.
- With `gh`, use `gh issue create`, `gh issue view <number> --comments`, `gh issue list`, `gh issue comment`, `gh issue edit`, and `gh issue close`.
- Preserve full issue bodies, comments, and labels when gathering ticket context.
- GitHub shares one number space across issues and pull requests; resolve ambiguous references before acting.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill mappings

- "Publish to the issue tracker" means create a GitHub issue.
- "Fetch the relevant ticket" means fetch the issue body, labels, and comments.
- Prefer structured connector operations in Codex; use `gh` when connector coverage is insufficient.

## Wayfinding operations

- A map is an issue labeled `wayfinder:map`.
- Child tickets use GitHub sub-issues where available, falling back to a task list and `Part of #<map>`.
- Child labels use `wayfinder:<type>`: `research`, `prototype`, `grilling`, or `task`.
- Use native issue dependencies where available; otherwise add `Blocked by: #<number>` to the child body.
- The frontier is the first unassigned open child without open blockers.
- Claim a ticket by assigning it to the driving developer.
- Resolve it by commenting with the answer, closing it, and adding a short linked decision to the map.
