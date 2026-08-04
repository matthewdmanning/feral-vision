# test_source_adapters.py

## Module-level tests

### test_hf_adapter_inspect_maps_hub_metadata_to_project_model_properties

Purpose: Verify Hugging Face metadata maps to project task outputs and preserved model metadata.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

### test_hf_adapter_fetches_only_missing_cached_weight_files

Purpose: Verify the Hugging Face adapter downloads only missing requested weight files.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

#### monkeypatch

### test_hf_adapter_explains_how_to_recover_when_metadata_is_unavailable

Purpose: Verify unavailable hub metadata produces an explicit instruction to opt into local fetching.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

### test_torch_hub_adapter_uses_configured_model_name_or_default

Purpose: Verify Torch Hub loading uses the configured weight name or its documented default with safe load options.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

#### weights

#### expected_name

### test_torch_hub_adapter_requires_explicit_local_inspection_fallback

Purpose: Verify Torch Hub inspection requires explicit local fetching when remote inspection is unavailable.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

### test_ultralytics_adapter_returns_module_and_preserves_task_metadata

Purpose: Verify the Ultralytics adapter exposes the downloaded PyTorch module and preserves task metadata.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

### test_ultralytics_adapter_rebuilds_detection_head_for_configured_taxonomy

Purpose: Verify an Ultralytics detector rebuilds its head for the configured class taxonomy while loading pretrained weights.

Load-bearing: False

Occurrence probability: 1

Rationale: The current detection Run Recipe preserves the source-default head;
this test covers an inactive later fine-tuning capability.

#### monkeypatch

### test_get_adapter_discovers_each_declared_source_adapter

Purpose: Verify every declared external model source resolves to the expected SourceAdapter implementation.

Load-bearing: True

Occurrence probability: 3

#### source

#### adapter_name

### test_get_adapter_explains_how_to_add_an_unknown_source_adapter

Purpose: Verify an unknown source fails with an actionable adapter-registration error.

Load-bearing: True

Occurrence probability: 2

#### default

### test_model_builder_delegates_remote_architecture_to_selected_adapter

Purpose: Verify remote model construction delegates the configured architecture to its selected source adapter.

Load-bearing: True

Occurrence probability: 3

#### monkeypatch
