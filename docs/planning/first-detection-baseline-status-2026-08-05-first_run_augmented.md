# First detection baseline status — 2026-08-05

## Scope

This document records the parts of the first two-class COCO-animal detection
Fine-tuning Baseline that are implemented or previously verified. It does not
claim that the cloud training run completed.

The cloud execution is an ephemeral private-GCE workflow: a new training VM
must be created for every run and must never be treated as a saved resource.

## Completed local implementation

| Area | Completed path | Result |
| --- | --- | --- |
| Run Recipe | `conf/runs/detection_first_run_augmented.yaml` | Selects the augmented COCO-animal Dataset Variant, `yolo11n_default`, detection training, MLflow tracking, and seeded annotation-aware augmentation. |
| Model source boundary | `src/feral_vision/models/sources/UltralyticsAdapter.py` | Loads the Ultralytics detector as the project-facing PyTorch `nn.Module`; model acquisition remains separate from task training. |
| Dataset Artifact contracts | `src/feral_vision/data/dataset_artifact.py` | Validates canonical payloads, Dataset Variant identity, source lineage, augmentation provenance, and version-aware tracker requirements. |
| Detection task boundary | `src/feral_vision/training/task_adapters/detection.py` | Provides variable-box collation, native target assignment, classification loss, generalized IoU loss, and detection metrics to the generic trainer. |
| Augmentation configuration | `conf/augmentation/coco_animals_detection_first_run_augmented.yaml` | Defines the seeded annotation-aware augmentation concern for the baseline. |
| Cloud training entrypoint | `scripts/runs/detection_first_run_augmented_container_train.sh` | Requires a staged Dataset Variant payload and managed MLflow URI, then launches `runs/detection_first_run_augmented` without DVC or in-container augmentation. |
| Detection image definition | `deploy/runs/detection_first_run_augmented/Dockerfile.gcp` | Embeds the repository, installs the Cloud Storage CLI/runtime dependencies, and starts the detection container entrypoint. |
| Detection image build | `deploy/runs/detection_first_run_augmented/cloudbuild.training-image.yaml` | Defines a regional, digest-pinned training-image build from an immutable base image. |
| Dataset staging | `terraform/runs/detection_first_run_augmented/templates/trainer_startup.sh.tftpl` | Pulls the selected immutable artifact payload and metadata to SSD, checks required files, checks CUDA, and launches training. |
| Ephemeral VM configuration | `terraform/runs/detection_first_run_augmented/main.tf`, `variables.tf`, `versions.tf`, `outputs.tf` | Isolates detection-run Terraform state and provisions one disposable GPU VM in `us-east4`. |
| Cloud preflight contracts | `scripts/cloud_preflight.py` | Validates immutable image/data references, Run Recipe composition, workload identity, MLflow endpoint, artifact access, and runtime identity before training. |

## Previously verified evidence

- The recorded local contract validation passed `170 passed, 1 skipped`; Ruff,
  mypy, formatting, and `git diff --check` also passed in the prior handoff.
- Regional Cloud Build image preparation had historical successes, including
  the source-agnostic DVC image and COCO acquisition image, with immutable
  digests recorded in `docs/planning/cloud-handoff.md`.
- The bounded COCO acquisition path completed remote export of 800 selected
  images in Cloud Build during the earlier preparation attempts.

These are partial implementation or preparation results. They are not a
completed detection Run Record.

## Cloud work still incomplete

The raw Dataset Artifact source is the COCO dataset download performed in
Google Cloud. Acquisition is cloud-only; the COCO payload is downloaded and
exported by the regional Cloud Build acquisition step, then published to
Cloud Storage. No local developer download is part of the artifact lineage.

Dataset payloads, manifests, and trackers belong in the dataset-only GCS
bucket, `mobile-training-images`; if a runtime needs the data, it downloads or
stages it from that bucket. The Artifact Registry repository stores container
images only and must never be used as Dataset Artifact storage.

The following acceptance evidence is still absent:

1. A published immutable raw COCO Dataset Artifact.
2. A published immutable annotation-aware Dataset Variant Artifact with a
   version-aware tracker and raw-artifact lineage.
3. A current digest-pinned detection training image.
4. A verified managed HTTPS MLflow endpoint and artifact prefix.
5. A fresh reviewed Terraform plan and creation of the ephemeral GPU VM.
6. Successful GPU training with the active detection Run Recipe.
7. An MLflow Run Record containing configuration, lineage, losses, checkpoint,
   and selected best Model Artifact.

The `storage.objects.create` prefix-scoped IAM grant for the Cloud Build
identity was submitted for
`datasets/coco/train2017/baseline-20260805-001/`; policy readback was not
observable in the current operator environment, so publication permission is
not yet treated as verified.

## Completion ledger

Every completed item must be added here with both the resulting path or
immutable identifier and the exact command that created or verified it. A
successful command without its output path, digest, or Run Record is not
acceptance evidence.

| Item | Status | Result path or ID | Creation or verification command |
| --- | --- | --- | --- |
| Raw Dataset Artifact | Pending | `gs://mobile-training-images/datasets/coco/train2017/<raw-revision>/` | `gcloud builds submit . --project=cs-poc-kewg0kffb7uwobgq1rex2af --region=us-east4 --config=deploy/cloudbuild.prepare.yaml --substitutions=_ACQUISITION_IMAGE=<immutable-acquisition-image>,_DVC_IMAGE=<immutable-dvc-image>,_DATASET_ARTIFACT_PREFIX=datasets/coco/train2017/<raw-revision> --quiet` |
| Annotation-aware Dataset Variant Artifact | Pending | `gs://mobile-training-images/datasets/coco/train2017/<variant-revision>/` | Record the exact materialization command and its input raw-artifact URI here; the current repository has the materializer and publisher contracts but no accepted cloud execution record. |
| Detection training image | Pending | `us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/<image>@sha256:<digest>` | `gcloud builds submit . --project=cs-poc-kewg0kffb7uwobgq1rex2af --region=us-east4 --config=deploy/runs/detection_first_run_augmented/cloudbuild.training-image.yaml --substitutions=_BASE_IMAGE=<immutable-base-image>,_TRAINING_IMAGE=us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/<image> --quiet` |
| MLflow endpoint and artifact prefix | Pending | `<https-endpoint>` and `<gs://artifact-prefix>` | Record the endpoint health check and the exact managed-service or infrastructure command that created it. Do not put credentials in this document. |
| Fresh Terraform plan | Pending | `/tmp/feral-vision-detection-first-run-augmented-<run-id>.tfplan` | `terraform -chdir=terraform/runs/detection_first_run_augmented init -reconfigure` followed by a reviewed `terraform plan -out=/tmp/feral-vision-detection-first-run-augmented-<run-id>.tfplan` with the resolved image, variant prefix, service account, zone, and MLflow URI variables. |
| Ephemeral training VM | Pending | `google_compute_instance.detection_first_run_augmented_trainer` and the created instance name | `terraform -chdir=terraform/runs/detection_first_run_augmented apply /tmp/feral-vision-detection-first-run-augmented-<run-id>.tfplan`; record the resulting Terraform output and instance name. |
| Cloud preflight | Pending | `artifacts/cloud-preflight-<run-id>.json` | `uv run python scripts/cloud_preflight.py --manifest <run-manifest>.json --output artifacts/cloud-preflight-<run-id>.json` |
| MLflow Run Record and Model Artifact | Pending | `<experiment>/<run-id>` and `<model-artifact-URI>` | Record the exact VM startup/training command plus the MLflow run ID, metrics, checkpoint URI, and selected best Model Artifact URI. |

Commands containing `<...>` are deliberately incomplete until the immutable
values are resolved. Replace them in this ledger with the final copy-paste
command after execution; never record mutable tags or guessed paths.

## Next execution sequence

1. Verify the dataset-writer binding and publish the raw and augmented
   artifacts under a new immutable, reviewed prefix.
2. Build and record the current detection image digest in `us-east4`.
3. Verify MLflow, service identity, image pull, dataset read, networking/NAT,
   and GPU capacity.
4. Generate and inspect a fresh detection-run Terraform plan.
5. Create the new ephemeral VM, inspect startup and training evidence, and
   retain the Run Record and Model Artifact.
6. Clean up the VM after evidence capture; do not retain the instance for the
   next run.

## Canonical references

- Run contract: `docs/runs/first-detection-baseline-first_run_augmented.md`
- Cloud operations history: `docs/planning/cloud-handoff.md`
- Training design handoff: `docs/planning/training-handoff-2026-08-01.md`
- Actionable cloud issue: GitHub issue `#65`
