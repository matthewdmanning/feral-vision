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
is defined in [the program flow](../../../docs/agents/program-flow.md).

During prep, the model-inspector MCP gathers provider information and saves
configuration, supported tasks, and provider metadata in the offline registry.
`get_model` returns that entry and its Hydra YAML. See the
[prep workflow](../../../docs/guide/quickstart.rst#model-inspector).
