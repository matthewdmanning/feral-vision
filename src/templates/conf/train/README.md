# Training configuration

## Purpose

Training configuration selects parameters for the canonical
`sightkit_learn.training.trainer` path.

## Selection

Choose a semantic training variant as part of a complete Run Recipe, including
its optimizer, scheduler, and loss concerns.

## Ownership

The trainer owns training flow and checkpoint behavior; this concern owns only
tunable values. The canonical boundary is defined in
[the program flow](../../../docs/agents/program-flow.md).
