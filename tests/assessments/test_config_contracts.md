# test_config_contracts.py

## Module-level tests

### test_recipe_composes_without_missing_values

Purpose: Verify every executable and testing Run Recipe resolves all required concerns and values.

Load-bearing: True

Occurrence probability: 3

#### recipe_path

### test_recipe_applies_valid_cli_overrides

Purpose: Verify supported structured CLI overrides change the selected batch size across Run Recipes.

Load-bearing: True

Occurrence probability: 3

#### recipe_path

#### batch_size

### test_test_recipe_is_cpu_safe

Purpose: Verify testing recipes select CPU execution and no background workers.

Load-bearing: True

Occurrence probability: 4

#### recipe_path

### test_recipe_rejects_unknown_structured_override

Purpose: Verify Run Recipes reject configuration fields outside their structured schemas.

Load-bearing: True

Occurrence probability: 2

#### default

### test_cloudbuild_config_composes_against_its_deploy_schema

Purpose: Verify cloud-smoke substitutions compose as typed declarative deployment inputs.

Load-bearing: True

Occurrence probability: 2

#### default

### test_cloudbuild_config_rejects_unknown_structured_override

Purpose: Verify cloud deployment inputs reject fields that the cloud-smoke workflow does not consume.

Load-bearing: True

Occurrence probability: 2

#### default

### test_model_variant_has_a_resolvable_source_location_and_schema

Purpose: Verify each selectable model declares an importable source, identifier, location, and valid output schema.

Load-bearing: True

Occurrence probability: 3

#### model_path
