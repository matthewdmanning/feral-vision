# Action items

Open work, most blocking first. Remove an item when it is done.

## Blocks the first GPU run

- **Verify Docker is available.** Start Docker Desktop if needed. Run the Docker tests with
  `scripts/docker_container_tests.sh` from a terminal; it prompts for approval,
  builds the deployment image, and runs pytest in Linux. Record the actual
  failures and results rather than assuming the earlier four failures persist.
- **Verify the training image.** Run `scripts/cloud/check_training_image.sh`
  with the project ID resolved from `PROJECT_NAME` in `.env.local`. Verify the
  selected digest supports the run's entrypoint and runtime requirements. Image age is not a build
  criterion. If a build is needed, use `scripts/cloud/build_training_image.sh`
  from a clean checkout. Billed Cloud Build run: needs approval.
- **Check sm_75 with GPU access.** Run the built image with `--gpus all` on
  an NVIDIA GPU host. Assert `torch.cuda.is_available()` and that `sm_75` is
  in `torch.cuda.get_arch_list()`. Without CUDA availability, this function
  returns an empty list; a CPU-only image build cannot prove this check.
  VM startup already checks the actual GPU's architecture before training;
  retain that gate and record its result for the T4 run.
- **Verify bucket configuration.** Check `TRAINING_DATA_BUCKET_URI` using
  the project ID resolved from `PROJECT_NAME` in `.env.local`. Reconcile
  Terraform's backend and operational output location separately; a check of a hard-coded operations
  bucket does not establish that the configured training data bucket is missing.
- **Finish `run.tfvars`.** Set `training_image` to the verified image digest.
  Confirm the service account, selected `dataset_artifact_prefix`, pinned
  `source_annotation_generation`, and separate operational `artifact_prefix`.
  Resolve the Dataset/annotation blockers below first. The file is gitignored.
- **Run preflight.** Run manually after reviewing the deployment inputs; never
  in CI. It performs live prerequisite checks and an operational write probe,
  and produces a saved plan plus deployment reports, not a running VM:

  ```bash
  python3 terraform/preflight/preflight.py --var-file terraform/runs/detection/run.tfvars
  ```

## Dataset and DVC remaining work

The previous fixed fetch/preprocess/augment ownership has been removed.
`dvc.yaml` and its wrappers are gone; existing data is preserved. Each selected
prepared Dataset is now registered independently by
[`scripts/data/register.sh`](scripts/data/register.sh) with `dvc add` and a
targeted `dvc push`. The publisher Dockerfile moved to
[`deploy/dataset-publisher/Dockerfile`](deploy/dataset-publisher/Dockerfile).
Repository-wide `dvc status --json` now succeeds. See
[the Dataset guide](docs/guide/dataset.rst) for the actual process and commands.

- **Configure and verify the real DVC remote.** The invalid tracked environment
  placeholder has been removed. Configure the dataset-only bucket's `/dvc`
  prefix as the default remote in `.dvc/config.local`. Credentials, permissions,
  and existing remote data have not been checked. Local registration/recovery
  was verified using a temporary repository and filesystem remote only.
- **Connect cloud publication to the registered DVC version.**
  `deploy/cloudbuild.prepare.yaml` still publishes a retained payload and
  manifest directly through `publish_dataset_artifact`, bypassing registration.
  Acceptance: register the exact Dataset selected for publication, preserve its
  `.dvc` metadata durably, and link the immutable training input to that version
  and its provenance. A pipeline lockfile is not required. Do not restore the
  removed broad output ownership or mutable whole-data synchronization.
- **Complete Dataset Variant publication.**
  `scripts/cloud/materialize_detection_variant.sh` imports the absent
  `publish_dataset_variant_artifact`. Acceptance: an annotation-aware Variant
  links its raw Artifact and records operations, resolved configuration, seed,
  and image order. Register each produced Dataset independently and reuse
  already verified inputs rather than rerunning completed production steps.
- **Reconcile training annotations before the first GPU run.** Variant
  materialization emits per-image YOLO `.txt` labels, while preflight and VM
  startup require `annotations/instances.json` with a pinned generation. The
  training loader pairs per-image annotations and has no COCO JSON loader.
  Acceptance: the same small published Artifact passes preflight, staging,
  loading, and one training batch with the intended class contract.

The removed `dvc.yaml` stages are not prerequisites for registering existing
Datasets. `preprocess` is a per-image function, and the legacy image-only
augmentation helper is not a Dataset Variant production contract.

## Documentation follow-up

- **Reassess the historical overlap audit if needed.**
  `docs/planning/agent-instructions-overlap-audit.md` records the 2026-08-01
  guide layout and cites files since removed. It is historical evidence, not
  a current instruction source; use `docs/agents/project_instructions.md`.

## Later

The following dependency/image targets are carried forward, not verified as
available or compatible by this DVC assessment.

- **Upgrade Python dependencies.** Stage 1: torch 2.14.1, torchvision 0.29.1,
  ultralytics, numpy and others. Drop the duplicate `opencv-python`. Hold the
  major version: opencv 5. The model inspector uses MCP 2.
- **Assess a base-image update.** Candidate: `nvidia/cuda` 13.4.2. Verify
  availability, compatibility, and its digest before changing the pinned base.
- **Add secret-scanning patterns.** GitHub custom patterns are not available
  through the API. Add them in the web UI if wanted.
