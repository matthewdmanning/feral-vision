# Configuration

Use this guide when changing Hydra configuration or model configuration.

Do not modify an existing Hydra `default.yaml` in place. Create a semantic named
replacement; the planned configuration cutover retires legacy defaults only
after the replacement recipes are validated. A required architecture `location`
must always be non-null so a model remains reproducible.

Consult the co-located configuration README for the concern's purpose and use a
complete named Run Recipe for reproducible work.

## Model and Run Recipe flow

`Model Source Adapter -> model (+ optional weights)`

Hydra owns tunable configuration and complete named Run Recipes. A Run Recipe
names the model and Dataset selected for training; a workflow script consumes
that configuration. The Run Recipe is information, not an actor in the
workflow.
