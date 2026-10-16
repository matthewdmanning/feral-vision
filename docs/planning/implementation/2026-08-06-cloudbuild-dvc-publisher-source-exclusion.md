# Cloud Build DVC publisher source exclusion

Date: 2026-08-06

## Failure

Cloud Build `1db2dd05-4ba0-4b91-b97b-e2d4337e341a` failed while building the
Cloud Run DVC publisher image. Docker could not copy
`src/feral_vision/data/dataset_artifact.py` because the submitted build context
excluded that tracked source file.

## Impact

No DVC publisher image was produced. The Cloud Run Job was not created or
executed, and the existing raw COCO payload was not finalized into a Dataset
Artifact.

## Correction and required verification

`.gcloudignore` now explicitly includes the required source path. Before a
retry, verify that `gcloud meta list-files-for-upload` includes the module; then
submit a new image build and deploy only its resolved digest.
