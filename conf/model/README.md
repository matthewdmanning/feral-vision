# Model configuration

## Purpose

Model configuration selects a reproducible model definition: architecture
source, identifier, location, and optional starting weights.

## Weights

A value of `null` for weights means the selected source supplies its default
weights; check the source documentation for their location. If the source
provides no weights, the model initializes random weights.

## Ownership

Model source adapters own source-specific behavior and inspected output
metadata; YAML must not duplicate that metadata. The model-acquisition boundary
is defined in [the program flow](../../docs/agents/program-flow.md).
