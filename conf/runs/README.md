# Run Recipes

## Purpose

Run Recipes are the only complete Hydra entrypoints.

## Selection

Use `baseline` for canonical local training and `smoke` for CPU-safe validation.
Select a different concern with a Hydra override, for example
`model=yolo11n_seg`.

## Ownership

Run Recipes compose the selected concerns; concern YAML files own their variant
values. The canonical execution path is defined in
[the program flow](../../docs/architecture/program-flow.md).
