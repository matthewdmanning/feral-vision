# Tracking configuration

## Purpose

Tracking configuration selects how a run connects to experiment tracking.

## Selection

Choose a semantic tracking variant as part of a complete Run Recipe.

## Ownership

MLflow owns run-generated metrics, artifacts, checkpoints, and run metadata;
DVC owns data artifacts. The complete ownership boundary is defined in
[ARCHITECTURE.md](../../ARCHITECTURE.md); issue #20 owns the remaining lineage
implementation.
