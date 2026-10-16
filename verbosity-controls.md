# Reducing verbosity, over-answering, and scope creep

Source: `claude-code-guide` agent, official docs. The `config-guide` skill covers @Claude in Slack and does not apply.

| Control | How | Doc |
|---|---|---|
| Concise output style | `/output-style concise` or `"outputStyle": "Concise"` in settings | code.claude.com/docs/en/output-styles.md |
| Custom output style | `.md` in `~/.claude/output-styles/` or `.claude/output-styles/`; `keep-coding-instructions: true` keeps coding behavior | same |
| Short CLAUDE.md | Under 200 lines. Exclude what code shows. Link, do not paste docs | code.claude.com/docs/en/memory.md |
| Path-scoped rules | `.claude/rules/*.md` with `paths:` frontmatter load only on matching edits | memory.md |
| Audit instructions | `/doctor prompt-audit` finds stale or conflicting rules | memory.md |
| Plan mode | `Shift+Tab` or `--permission-mode plan`. Skip for one-sentence diffs | best-practices.md |
| UserPromptSubmit hook | `additionalContext` injects a brevity or scope reminder each prompt | hooks.md |
| Stop hook | Runs a check before the turn ends; can block it | hooks.md |
| Subagent and skill descriptions | Short, specific triggers. `disable-model-invocation: true` for manual-only skills | subagents.md, skills.md |
| Scoped prompts | Name the file, the scenario, and what "done" means. Give a verify step | best-practices.md |

## Unverified

- Whether positive rules ("do X") beat negative rules ("do not X").
- Measured token savings per setting.
- The agent's Stop hook JSON snippet. Its shape (flat entry, `onFailure` field) looks wrong. Check hooks.md before copying.
