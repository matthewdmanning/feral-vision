# test_dataset_artifact.py

## Module-level tests

### test_publish_dataset_artifact_uploads_payload_and_manifest

Purpose: Verify canonical dataset payload files and a generation-guarded manifest are published together.

Load-bearing: True

Occurrence probability: 3

#### payload_root

#### input_path

### test_publish_dataset_artifact_rejects_missing_provenance

Purpose: Verify publication rejects acquisition metadata without provenance.

Load-bearing: True

Occurrence probability: 2

#### payload_root

#### tmp_path

### test_publish_dataset_artifact_rejects_noncanonical_payload

Purpose: Verify publication rejects payloads missing the required annotations directory.

Load-bearing: True

Occurrence probability: 2

#### input_path

#### tmp_path

### test_publish_dataset_tracker_uploads_generated_dvc_file

Purpose: Verify the generated DVC tracker is uploaded under the dataset artifact prefix.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_publish_dataset_variant_records_immutable_source_artifact_lineage

Purpose: Verify a Dataset Variant Artifact records its immutable source artifact and annotation-aware operation.

Load-bearing: True

Occurrence probability: 3

#### payload_root

#### input_path

### test_preparation_config_requires_separate_immutable_images

Purpose: Verify acquisition and DVC publication use separate stages and keep training dependencies out of the publisher image.

Load-bearing: True

Occurrence probability: 2

Rationale: This is a configuration smoke test; it does not execute the built
images or prove the remote publication boundary.

#### default
