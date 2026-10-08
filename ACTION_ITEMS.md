# Action items

Open work, most blocking first. Remove an item when it is done.

## Blocks the first GPU run

- **Start Docker.** Start Docker Desktop. Then run the Docker tests with
  `scripts/docker_container_tests.py`. Confirm the 4 tests that fail on Windows
  pass on Linux.
- **Rebuild the image.** The newest image in Artifact Registry
  (`feral-vision-gcp:detection-20260813`) predates
  `scripts/runs/container_train.sh`. Run
  `scripts/cloud/check_training_image.sh` first. Build with
  `scripts/cloud/build_training_image.sh` from a clean checkout. Billed Cloud
  Build run: needs approval.
- **Check sm_75 in the image.** In the built image, run
  `python -c "import torch; print(torch.cuda.get_arch_list())"`. Expect `sm_75`.
- **Create the operations bucket.** `gs://feral-vision-operations-us-east4`
  returns 404. It is the Terraform backend and the `artifact_prefix` bucket.
  Preflight and apply cannot run without it. Needs approval.
- **Finish `run.tfvars`.** Set `training_image` to the digest from the rebuild.
  Confirm the service account and `artifact_prefix`. The file is gitignored.
- **Run preflight.** Run `terraform/preflight/preflight.py --var-file
  terraform/runs/detection/run.tfvars` by hand. Never in CI.

## Decisions needed

- **Remove Terraform tests?** Delete the 3 pytest tests that read Terraform
  files, and `terraform/tests/`? Terraform is not source code and not a test.
- **Pick publication flow.** `docs/guide/dataset.rst`, `docs/agents/data.md` and
  the code describe three different Dataset Artifact publication flows. Choose
  one. Fix the others.
- **Add publisher code.** No code in `src/` writes `dataset-artifact.json`. The
  published artifacts have one. Decide where the writer lives.

## Broken or stale code

- **Fix the materialize script.** `scripts/cloud/materialize_detection_first_run_augmented.sh`
  imports `publish_dataset_variant_artifact` and `publish_dataset_tracker`.
  Neither exists.
- **Fix the DVC fetch root.** The default recipe sets `data.root` to
  `data/augmented/coco-animals-v1`. The `dvc.yaml` fetch stage outputs
  `data/raw`.
- **Fix `dataset.rst`.** Lines 70-79 say the training VM creates `dvc.lock`. Lines
  49-68 describe a publisher that does not exist. Lines 9-12 list `.json` labels
  that have no loader.
- **Update `agent-instructions-overlap-audit.md`.** It cites guides that do not
  exist.

## Git and branches

- **Commit the HF update.** Branch `chore-huggingface-hub-update` has uncommitted
  changes: `pyproject.toml`, `uv.lock`, `tests/test_source_adapters.py`. Two
  commits: `build:` and `test:`. Merge it back into this branch.
- **Clean up the backup.** Remove branch and worktree
  `chore-huggingface-hub-update-from-main` with `safe-worktree-cleanup`.
- **Sort the pending edits.** These are uncommitted and not part of this work:
  `src/feral_vision/data/augmentations.py`, `fetch.py`,
  `tests/test_image_operations.py`, `.githooks/pre-commit`, `.gitignore` edits
  (`*.local*`, `.local/`, `*.pt`), `scripts/docker_container_tests.py`,
  `skills-lock.json`, `.agents/`.

## Later

- **Upgrade Python dependencies.** Stage 1: torch 2.14.1, torchvision 0.29.1,
  ultralytics, numpy and others. Drop the duplicate `opencv-python`. Hold the
  major versions: opencv 5, mcp 2.
- **Bump the base image.** `nvidia/cuda` 13.4.2 is newer. No digest was found.
- **Add secret-scanning patterns.** GitHub custom patterns are not available
  through the API. Add them in the web UI if wanted.
- **Update the MCP route.** The `model-inspector` server timed out on connect.
  Test it before agents rely on the router row.
