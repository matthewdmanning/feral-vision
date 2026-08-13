# First augmented detection cloud orchestration

## Scope

This implementation adds the operator scripts and immutable contracts for the
first `first_run_augmented` YOLO11n detection run. It does not create MLflow,
alter IAM, submit a build, apply Terraform, or claim a completed training run.

## Workflow

`scripts/cloud/prepare_detection_first_run_augmented.sh` accepts an MLflow
artifact prefix and existing VM service-account email through the invoking
environment. It verifies the existing raw Artifact,
builds or resolves the run-specific image digest, materializes an immutable
annotation-aware Dataset Variant, records a version-pinned DVC tracker URI, and
creates a fresh Terraform plan beside `run-manifest.json`.

The Variant materializer maps COCO `cat` annotations to YOLO class `0` and all
other selected animal annotations to class `1` (`not-cat`). It does not mutate
the raw Artifact.

After plan review, `scripts/runs/detection_first_run_augmented.sh` applies that
exact plan, captures startup output, and queries MLflow by the run-specific
`feral_vision_run_id` tag. Generated evidence belongs under
`artifacts/detection_first_run_augmented/<run-id>/` and is ignored by Git.

## Required external inputs

- A writable MLflow artifact prefix. The tracking URI is created locally on the
  disposable VM and is not supplied by the operator.
- An existing VM identity with the reviewed image-pull, Variant read, and
  MLflow-artifact write permissions.
- An authenticated Terraform and gcloud operator in
  `cs-poc-kewg0kffb7uwobgq1rex2af`.

## Validation status

Static and focused local tests validate the binary label conversion and the
Cloud Build/Terraform contracts. Remote image publication, Variant publication,
Terraform apply, and MLflow Run Record collection remain operational evidence
to capture when the supplied external inputs are available.
