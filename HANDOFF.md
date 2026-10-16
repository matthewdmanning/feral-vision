# Handoff

Written 2026-10-08. Branch `claude/terraform-gcp-dataset-training-6j1tko`, HEAD `742b24c`. Nothing is pushed.

## Where the project stands

- The Terraform root `terraform/runs/detection/` plans one on-demand `n1-standard-4` VM with one T4 and one NVMe Local SSD.
- No GPU run has happened. Four things stop the first run:
  1. **Verify image requirements.** Check Artifact Registry and verify the selected digest supports the run. Image age does not require a build.
  2. **Verify bucket configuration.** Use `TRAINING_DATA_BUCKET_URI` from `.env.local` for the training data bucket check. Resolve `PROJECT_NAME` to its project ID before passing `--project`. Reconcile the Terraform backend and operational output location separately.
  3. **Docker is down.** The Docker pre-push tests have not run on this machine.
  4. **Unfinished `run.tfvars`.** `training_image` is deliberately unset. Three values are assumptions (service account, `artifact_prefix`, dataset prefix). The file is gitignored. `.agents/secrets.md` maps its keys.
- T4 with the locked torch 2.12.1 cu13 wheels: a subagent found CUDA 13.0 and the PyTorch cu13 build matrix support `sm_75`. Driver 580 is enough. `torch.compile` and Triton on Turing are unverified. The repo uses no bf16 or compile. The `verify_gpu` startup stage now asserts `sm_75` is in `torch.cuda.get_arch_list()`. This is not yet tested on a VM.

## Rules from the user (hard)

- **Terraform is never in CI.** Terraform, `terraform test` and `terraform/preflight/preflight.py` never run in a workflow, a git hook or `scripts/validate_ci.sh`. They are not source code and not tests. Today none of them does.
- **Check for the image first.** Run `scripts/cloud/check_training_image.sh` before you say the image is missing, and before any build. See `docs/agents/cloudops.md`. Earlier agents built an image, forgot, and claimed it did not exist.
- **There is no "deployment contract".** Do not cite one. Do not treat `tests/test_training_deployment.py` as authoritative. Another agent wrote it.
- **No Windows workarounds.** Linux and Docker are the target.
- **Do not touch the user's pending edits** (list below). Stage explicit paths only. Never `git add -A`.
- **No cloud change without approval.** A Cloud Build run, a bucket and an apply each need a yes.
- **Report format.** Short reports. Load-bearing result first. Action items last, each with a 2-4 word blurb. No per-file change lists.
- **Prose style.** ASD-STE100: short active sentences, one instruction each.
- **The repository is public.** Do not commit the project ID in new files, service account emails, bucket names, annotation generations or digests of private images.

## Tooling traps

- The Bash tool's pre-tool hook runs the full pytest suite and blocks every command on 4 known failures (2 `WinError 193` on a `.sh` script, 2 `mask.ndim`). Use PowerShell for git and tests.
- Run tests with `uv run python -m pytest`, never `uv run pytest`.
- Terraform binary: `C:\Users\mattm\AppData\Roaming\terraform\terraform.exe`. A `terraform init` on Windows adds platform hashes to the `.terraform.lock.hcl` files. Restore them with `git checkout` unless you mean to commit them.
- The `.githooks/pre-commit` hook runs ruff on `src` and `tests`.
- `gcloud` work: load the `gcloud` skill. Run `gcloud help <command>` first. Single commands, `--project`, `--quiet`, no pipes.

## Uncommitted work that is not part of this handoff

`src/feral_vision/data/augmentations.py`, `src/feral_vision/data/fetch.py`, `tests/test_image_operations.py`, the staged `.githooks/pre-commit`, the user's `.gitignore` edits (`*.local*`, `.local/`, `*.pt`), `scripts/docker_container_tests.py`, `skills-lock.json` and `.agents/`.

## Other branches

- `chore-huggingface-hub-update` (worktree `.claude/worktrees/chore-huggingface-hub-update`): `huggingface-hub` 2.2.0, `albumentations==2.0.8`, and real-client Hugging Face tests. Uncommitted. Plan: a `build:` commit and a `test:` commit, then merge back here.
- `chore-huggingface-hub-update-from-main`: a backup. Remove it with the `safe-worktree-cleanup` skill. Never force.

## Known code problems found, not fixed

- `scripts/cloud/materialize_detection_first_run_augmented.sh` imports two functions that do not exist in `src/`.
- No code in `src/` writes `dataset-artifact.json`. The published artifacts have one. Preflight and the trainer require it.
- `docs/guide/dataset.rst` is wrong in three places (VM creates `dvc.lock`, a publisher that does not exist, `.json` labels with no loader).
- The default recipe `data.root` does not match the `dvc.yaml` fetch output.

## Action items

The full list is `ACTION_ITEMS.md`, most blocking first.

- **Start Docker.** Run the Docker tests. Confirm the 4 failures pass on Linux.
- **Verify the image.** Run the check script and verify the selected digest against the run requirements. A billed build needs approval if required.
- **Verify bucket configuration.** Use `.env.local`, then reconcile Terraform inputs and run preflight by hand.
- **Decide Terraform tests.** Keep or delete the 3 pytest tests that read Terraform files, and `terraform/tests/`.
- **Decide publication flow.** Pick the one flow `dataset.rst` and `data.md` describe.
