# First detection baseline cloud handoff — 2026-08-05

## Objective

Create the first two-class COCO-animal Dataset Artifact entirely in Google
Cloud, then create the annotation-aware Dataset Variant and run the detection
baseline on a newly created, disposable private-GCE training VM.

The training VM must be created for every run. It is never a saved or
persistent resource.

## Storage and lineage rules

- COCO is downloaded remotely by regional Cloud Build.
- Dataset payloads, manifests, and DVC trackers belong in the dataset-only
  bucket `gs://mobile-training-images/`.
- Artifact Registry stores container images only. It must never be used as
  Dataset Artifact storage.
- The intended first raw-artifact prefix is
  `datasets/coco/train2017/baseline-20260805-001/`.
- Training must consume the later immutable Dataset Variant prefix, not the
  raw artifact.
- Cloud Build and training remain regional in `us-east4`.

## Completed implementation paths

- Run Recipe: `conf/runs/detection_first_run_augmented.yaml`
- Dataset Artifact contracts: `src/feral_vision/data/dataset_artifact.py`
- Annotation-aware detection materializer:
  `src/feral_vision/data/augmentations.py`
- Detection Task Adapter: `src/feral_vision/training/task_adapters/detection.py`
- Remote COCO acquisition: `scripts/cloud/acquire_coco_subset.sh`
- Dataset Artifact publisher: `scripts/cloud/publish_dataset_artifact.sh`
- Preparation workflow: `deploy/cloudbuild.prepare.yaml`
- Acquisition image: `deploy/Dockerfile.coco-acquire`
- DVC publisher image: `deploy/Dockerfile.dvc`
- Detection image: `deploy/runs/detection_first_run_augmented/Dockerfile.gcp`
- Detection image build: `deploy/runs/detection_first_run_augmented/cloudbuild.training-image.yaml`
- Ephemeral VM: `terraform/runs/detection_first_run_augmented/`
- VM startup/staging: `terraform/runs/detection_first_run_augmented/templates/trainer_startup.sh.tftpl`
- Preflight: `scripts/cloud_preflight.py`

## Commands and observed results

### Prefix-scoped writer grant

Command submitted:

```bash
gcloud storage buckets add-iam-policy-binding gs://mobile-training-images --member="serviceAccount:feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com" --role="roles/storage.objectCreator" --condition="title=baseline-dataset-prefix,expression=resource.name.startsWith('projects/_/buckets/mobile-training-images/objects/datasets/coco/train2017/baseline-20260805-001/'),description=Allow Dataset Artifact object creation only under the reviewed immutable baselineprefix" --quiet
```

Observed result: command returned without an error, but the subsequent
policy readback produced no output in the operator environment. Treat the
binding as unverified until a readback or successful publisher write proves
it. This binding is for the Cloud Build identity above; it is not proof that
the Compute Engine VM identity has dataset access.

### Failed Dataset Artifact preparation

Command submitted:

```bash
gcloud builds submit . --project=cs-poc-kewg0kffb7uwobgq1rex2af --region=us-east4 --config=deploy/cloudbuild.prepare.yaml --substitutions=_ACQUISITION_IMAGE=us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-coco-acquire@sha256:47de9228e3c9f143c3db87eed1660463fdb4cec115297e1283f784bc80d60baf,_DVC_IMAGE=us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-dvc@sha256:49e9662ed0376be69107b4e3543c8ebfbfc90c9ff4b0499ccc600628d09323e8,_DATASET_ARTIFACT_PREFIX=datasets/coco/train2017/baseline-20260805-001 --quiet
```

Build ID: `468f0271-f38c-493f-a081-8a228ba1f628`

Result: `FAILURE` at `2026-08-05T19:13:55Z`.

Cloud Build reported that step 0 could not pull the COCO acquisition image
after ten retries. The DVC publisher step stayed queued and never ran. A
read-only Artifact Registry lookup independently returned `NOT_FOUND` for the
submitted COCO digest, so this digest must not be retried.

No Dataset Artifact objects, manifest, or tracker were verified under the
target prefix.

### Failed publisher-image builds

The DVC publisher image was attempted with:

```bash
gcloud builds submit . --project=cs-poc-kewg0kffb7uwobgq1rex2af --region=us-east4 --config=deploy/cloudbuild.dvc-image.yaml --substitutions=_DVC_IMAGE=us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-dvc:baseline-20260805 --quiet
```

Observed regional builds:

- `3396484a-f5f5-48e1-9f71-3c363c4568db` — `FAILURE`, Docker step failure.
- `afe7c9c4-587e-4b52-bd5c-466218b0ab25` — `FAILURE`, Docker step failure.

The final Docker error was not captured. The tag and digest must be checked
in Artifact Registry after a successful rebuild; neither failed build
produced a usable publisher image.

## Blocking information

1. The current COCO acquisition digest is absent from the current Artifact
   Registry repository. Historical digests in `docs/planning/cloud-handoff.md`
   are not sufficient evidence of current availability.
2. The DVC publisher image cannot currently be used because both recent image
   builds failed in their Docker step.
3. The exact Docker failure is unresolved because Cloud Build log retrieval
   returned no usable payload in this environment. Inspect build logs for the
   two IDs above before retrying.
4. The writer IAM grant was submitted but not independently verified.
5. No raw Dataset Artifact exists at the target prefix based on the evidence
   captured in this session.
6. The annotation-aware Dataset Variant still needs a real cloud materialize
   and publish execution. Its exact cloud command and resulting prefix have
   not yet been recorded.
7. The current detection image digest has not been built or recorded.
8. The managed HTTPS MLflow endpoint and artifact prefix are still unknown.
9. The VM service account, image-pull permission, dataset-read permission,
   private networking/NAT, and available GPU capacity must be reverified.
10. Terraform provider initialization/plan for `terraform/runs/detection_first_run_augmented/`
    has not been completed for this run.

## Required recovery sequence

1. Inspect Cloud Build failure details for
   `3396484a-f5f5-48e1-9f71-3c363c4568db` and
   `afe7c9c4-587e-4b52-bd5c-466218b0ab25`; determine whether the Docker
   failure is base-image access, dependency download, or Artifact Registry
   push permission.
2. Build the COCO acquisition and DVC publisher images in the current
   `us-east4` repository using the current source. Verify each tag resolves to
   an existing digest before submission.
3. Re-read the bucket IAM policy or prove the writer grant with a scoped
   publisher write. Do not broaden the grant.
4. Submit `deploy/cloudbuild.prepare.yaml` with the newly verified immutable
   image digests and the reviewed raw prefix.
5. Verify all of the following before proceeding:
   `payload/images/`, `payload/annotations/`, `dataset-artifact.json`, and
   `dataset-artifact.dvc` containing `version_id`.
6. Materialize and publish the annotation-aware Dataset Variant from the raw
   artifact; record its exact command, source URI, output prefix, manifest,
   and tracker.
7. Build and record the digest-pinned detection training image.
8. Resolve MLflow, service identity, dataset read, image pull, network/NAT,
   and GPU capacity prerequisites.
9. Generate and inspect a fresh Terraform plan; do not reuse saved plans.
10. Create one new ephemeral VM, run preflight, launch the detection recipe,
    capture the MLflow Run Record and Model Artifact, and clean up the VM.

## Acceptance evidence to append

For every completed step, append the exact command and the immutable result:

- Cloud Build ID and terminal status
- GCS prefix and object listing
- image digest and Artifact Registry path
- Dataset Artifact manifest and tracker `version_id`
- Variant-to-raw lineage URI and augmentation recipe
- Terraform plan path and resource count
- VM instance name and startup/preflight evidence
- MLflow experiment/run ID, metrics, checkpoint, and Model Artifact URI

Do not mark the cloud baseline complete from local tests, a successful image
build, a successful COCO export, or a VM creation alone.

## Source documents

- `docs/planning/first-detection-baseline-status-2026-08-05-first_run_augmented.md`
- `docs/planning/cloud-handoff.md`
- `docs/runs/first-detection-baseline-first_run_augmented.md`
- GitHub issue `#65`
