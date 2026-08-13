# User interactions

## Scope

Use this guide for interactions with users: chat and summary output intended
for users, including when an operator must make a change through a command-line
interface. It does not govern messages intended for other agents.

## Collaboration preferences

- Be direct, concise, high-information, and evidence-led. Distinguish verified
  results from assumptions or partial validation.
- Do not give a status-only handoff. When blocked, name the exact blocker,
  permission, credential, or decision required to continue.
- Preserve unrelated worktree changes and do not broaden the requested scope
  without direction.
- When clarifying terminology, ask about one concrete object at a time; do not
  promote a proposed umbrella term to canonical vocabulary.

## Cloud Job communication

When explaining the project pipeline to users, describe the data flow, model
flow, Cloud Job, and its concrete outputs. Do not replace that explanation with
run-specific configuration or Cloud Operations internals.

## CLI boundary

Never integrate a CLI into a function or Python script. Only shell scripts may
provide command-line interfaces.

When an operator must make a change, provide the exact complete CLI command in
a standalone `bash` code block. Commands must be directly copy/paste compatible
and include every required flag and value.
