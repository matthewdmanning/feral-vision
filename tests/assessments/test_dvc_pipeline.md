# test_dvc_pipeline.py

## Module-level tests

### test_dvc_pipeline_declares_only_documented_data_stages

Purpose: Verify DVC declares only the documented fetch, preprocess, and augment stages with the expected dependencies and outputs.

Load-bearing: True

Occurrence probability: 2

Rationale: Pipeline definition changes are infrequent, and this test checks the
declarative graph only; it does not run DVC or publish an artifact.

#### dvc_pipeline

#### dvc_data_stage
