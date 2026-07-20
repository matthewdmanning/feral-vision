# Scheduler configuration

## Purpose

Scheduler configuration selects the learning-rate schedule used by the
canonical trainer.

## Selection

Choose a semantic scheduler variant through the training concern in a complete
Run Recipe.

## Ownership

Training code owns scheduler construction. The canonical training path is
defined in [ARCHITECTURE.md](../../../ARCHITECTURE.md).
