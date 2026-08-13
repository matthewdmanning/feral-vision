# test_dataset_artifact.py

## Module-level tests

### test_version_dataset_records_folder_in_lockfile

Purpose: Verify a Dataset folder is added to DVC, recorded as a stage dependency,
and reproduced into `dvc.lock`.

Load-bearing: True

Occurrence probability: 3

#### payload_root

### test_publish_dataset_lock_uploads_only_lockfile

Purpose: Verify Dataset publication uploads only `dvc.lock` as the Dataset
version record.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_publication_script_pushes_dataset_before_its_lockfile

Purpose: Verify the Cloud Job pushes DVC-managed Dataset data before making the
lockfile available to training.

Load-bearing: True

Occurrence probability: 3

### test_publish_dataset_lock_rejects_non_lockfile

Purpose: Verify Dataset publication rejects missing or non-`dvc.lock` metadata.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_preparation_config_requires_separate_immutable_images

Purpose: Verify acquisition and DVC publication use separate stages and keep training dependencies out of the publisher image.

Load-bearing: True

Occurrence probability: 2

Rationale: This is a configuration check; it does not execute the built
images or prove the remote publication boundary.

#### default
