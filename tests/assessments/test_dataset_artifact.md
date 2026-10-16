# test_dataset_artifact.py

## test_publish_dataset_artifact_uploads_payload_then_manifest

Purpose: Verify every payload file is uploaded with create-only generation
preconditions and retention, followed by the manifest containing file hashes
and generations.

Load-bearing: True

Occurrence probability: 3

Fixtures: `dataset_root`, `tmp_path`, in-memory storage client.

## test_publish_dataset_artifact_rejects_empty_input

Purpose: Reject an empty metadata object before cloud writes.

Load-bearing: True

Occurrence probability: 3

Fixtures: `dataset_root`, `tmp_path`.

## test_publish_dataset_artifact_rejects_input_that_defines_files

Purpose: Prevent caller metadata from supplying the publisher-owned file list.

Load-bearing: True

Occurrence probability: 3

Fixtures: `dataset_root`, `tmp_path`.

## test_publish_dataset_artifact_rejects_zero_retention

Purpose: Reject publication without a positive retention interval.

Load-bearing: True

Occurrence probability: 3

Fixtures: `dataset_root`, `tmp_path`.

## test_publication_script_publishes_without_dvc

Purpose: Document that the existing cloud publisher invokes the payload/manifest
API directly; it does not prove the outstanding DVC integration.

Load-bearing: False

Occurrence probability: 2

## test_preparation_config_requires_separate_immutable_images

Purpose: Check acquisition/publication separation and exclusion of training and
source-specific dependencies from the renamed publisher Dockerfile. The test
does not execute images or enforce digest pinning.

Load-bearing: True

Occurrence probability: 2
