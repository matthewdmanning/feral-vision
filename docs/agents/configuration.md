# Configuration

Use this guide when changing Hydra configuration or model definitions.

Do not modify an existing Hydra `default.yaml` in place. Create a semantic named
replacement; the planned configuration cutover retires legacy defaults only
after the replacement recipes are validated. A required architecture `location`
must always be non-null so a model remains reproducible.

All tunables belong in `conf/`. Consult the co-located configuration README for
the concern's purpose and use a complete named Run Recipe for reproducible work.
