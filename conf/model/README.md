# Model configuration

## Purpose

Model configuration selects a reproducible model definition: architecture
source, identifier, location, and optional starting weights.

## Selection

Choose a semantic model variant as part of a complete Run Recipe.

## Ownership

Model source adapters own source-specific behavior and inspected output
metadata; YAML must not duplicate that metadata. The model-acquisition boundary
is defined in [the program flow](../../docs/architecture/program-flow.md).
