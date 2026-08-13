# Test audit report

Date: 2026-08-02

## Evidence

- Scope: 16 `tests/test_*.py` modules and 90 module-level test functions.
- Assessment bookkeeping: 16 assessment files exist; every discovered test and
  fixture is represented exactly once.
- Execution: `167 passed, 1 skipped` with two warnings.
- Measured source coverage: 1,217 of 2,165 statements, or 56%.
- The existing staged deletions were left unchanged.

The passing suite proves that the current examples execute. It does not prove
that the supported workflow is protected end to end, and the assessment labels
must not be read as a test-quality score.

## Findings requiring discipline

1. `test_write_augmentation_preview_html_creates_structured_grid_assets`
   checks exact CSS and JavaScript strings. This is a brittle implementation
   snapshot for optional human-review tooling, so it is not load-bearing.
2. `test_source_partition_slices_are_complete_contiguous_and_ordered` reads
   the private `_index` field. It can pass while the public `load()` behavior is
   broken and should be treated as partial coverage.
3. `test_preparation_config_requires_separate_immutable_images` uses negative
   substring checks against a Dockerfile. Those checks are useful lightweight signals,
   but they do not establish that the built image or Cloud Build execution has
   the required boundary.
4. `test_fit_trains_bbox_net_toward_real_annotation_boxes` does not test
   "toward" or convergence. It only checks finite history and that an optimizer
   changed parameters; its assessment purpose has been narrowed to that actual
   contract.
5. `test_cloud_preflight.py` covers only a successful Compute request. It does
   not prove status handling, identity validation, or readiness of a running
   training job.
6. `test_dvc_pipeline.py` inspects YAML only. It does not execute DVC or prove
   Dataset Artifact publication and lineage.

## Important untested production surface

Coverage identifies no exercised lines in `FeralDataset.py`,
`augmentation_preview_app.py`, `coco_to_yolo.py`, `creator.py`,
`schema_convert.py`, or `main.py`. The audit also found no tests for
`utils.to_dtype`, the augmentation-stage runner, or the optional distillation
branch in `training/losses.py`. These are coverage gaps, not evidence that the
implementations are correct or incorrect.

## Assessment policy applied

`Load-bearing` means the scenario protects a supported production contract,
data/model lineage guarantee, safety boundary, or materially invalidating
failure. It does not mean the test is strong. Optional preview presentation,
fixture-only checks, cached-value shortcuts, and the inactive
Ultralytics head-rebuild capability are marked false. Occurrence scores describe
the production scenario, not pytest frequency; rare configuration and recovery
paths are scored 1–2 even when their tests are valuable.
