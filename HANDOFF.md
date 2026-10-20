# Handoff

Written 2026-10-20. Branch `review/google-cloud`, pushed HEAD `80c0911`. The previous handoff (2026-10-08) is in git history at `dcaa0b9`.

## Where the project stands

- No GPU run has happened. Nothing in this session ran in Docker or on a GPU.
- Pushed this session:
  - `97b327a`, `54453f3`, `d9e8eb3`: deploy check, Google Cloud skill rules, hydra `outputs/` untracked.
  - `80c0911`: test suites removed from the GPU training path. Only existence checks for required resources remain. The GPU e2e suite moved to the pre-push Docker build (`tools/docker_container_tests.sh`).
- **Training outputs go to the existing bucket** (committed after `80c0911`). Both trees (`feral-vision/` and `src/templates/`):
  - `container_train.sh` now `exec`s `cloud_train.sh` with `RUN_OUTPUT_DIR=/data/outputs`.
  - `cloud_train.sh` and `run_outputs.py` upload all outputs to `<artifact_prefix>/<run_id>/instances/<VM instance ID>/<attempt>/`. Before this change, the checkpoint and MLflow artifacts stayed in the container and `--rm` deleted them.
  - `run_outputs.train()` takes an optional `overrides` list.
  - Startup template passes `TRAINING_DATA_BUCKET_URI="$run_artifact_uri"` and no longer copies MLflow files itself.
  - `check_training_e2e.sh` calls `run_outputs.train` directly. The upload needs the GCE metadata server.
  - Lint, format and `bash -n` pass. No test ran.

## Verified this session

- torch 2.12.1 / torchvision 0.27.1: compatible (torchvision README).
- torch 2.12 stable CUDA 13.0 build: cuDNN 9.20.0.48 and NCCL 2.29.7 match `uv.lock` exactly (PyTorch `RELEASE.md`).
- Boot image family `pytorch-2-9-cu129-ubuntu-2204-nvidia-580`: `READY`, image `v20261019`, driver branch r580. r580 supports CUDA 13.0. The exact 580.x version and the NVIDIA Container Toolkit are not visible in image metadata.
- No step in the startup script repeats an install from the image.

## Rules from the user (hard)

- **Only essential checks in the GPU path.** Existence checks for required resources are allowed. Regression tests run in the pre-push Docker build.
- **Use the existing bucket for outputs.** Do not propose a new bucket.
- **Terraform is never in CI.** Terraform and `preflight.py` never run in a workflow, a git hook or a test.
- **Check for the image first.** Run `scripts/cloud/check_training_image.sh` before you say the image is missing.
- **No Windows workarounds.** Linux and Docker are the target.
- **Docker tests need approval.** The script prompts on `/dev/tty`, so the user runs it.
- **The repository is public.** Do not commit project IDs, service account emails, bucket names or private digests.
- **Google Cloud work:** load `google-cloud-recipe-auth` first. Use the `gcloud` skill: `gcloud help <leaf>` first, `--project`, `--quiet`, no pipes.
- **Prose style.** ASD-STE100. Decisions last, active verbs.

## Tooling traps

- The local Windows `.venv` torch install is damaged: 6,410 files from its `RECORD` are missing, including `torch/amp`. Every pytest run fails at `tests/conftest.py:6`. Fix: `uv sync --reinstall-package torch` (about 2–3 GB; disk space is tight).
- No disk space for the Docker pre-push build now.
- Run tests with `uv run python -m pytest`, never `uv run pytest`.
- `git worktree remove` fails with "Permission denied" if the session's working directory is inside that worktree.

## Open branches

- `docs-module-layout` and `claude/terraform-gcp-dataset-training-6j1tko`: not fully merged. Remote is gone. The user decides; a hook blocks `git branch -D`.

## Decisions

- **Review the output transfer code in `scripts/runs/run_outputs.py` with `google-cloud-storage-basics`.** That skill became available after the code was written. The project rules require it for Cloud Storage transfers.
- **Run `tools/docker_container_tests.sh` when disk space allows.** The GPU e2e step and `tests/test_cloud_run_outputs.py` are the only checks of this change.
- **Decide whether `google-cloud-storage` becomes a direct dependency in `pyproject.toml`.** `run_outputs.py` imports it, but only a transitive lock entry installs it (`uv.lock:1754`).
