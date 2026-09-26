# Feral Vision instructions for Codex

Before working in this repository, read the canonical
[project instructions](docs/agents/project_instructions.md).

## Canonical GPU training path

There is one supported GPU training path. Do not create a sibling deployment,
run-specific copy, alternate Dockerfile, or alternate Run Recipe.

- Training recipe: `conf/runs/detection.yaml`
- Training image: `deploy/Dockerfile.gcp`
- Cloud Build: `deploy/cloudbuild.training-image.yaml`
- Image build entrypoint: `scripts/cloud/build_training_image.sh`
- Terraform root: `terraform/runs/detection/`
- Deployment preflight: `terraform/preflight/preflight.py`
- Apply/evidence launcher: `scripts/runs/detection.sh`
- Container entrypoint: `scripts/runs/container_train.sh`

The repository preflight deliberately fails if a second training Run Recipe,
training `Dockerfile.gcp`, or container-training entrypoint is introduced.

The training image uses a digest-pinned NVIDIA CUDA 13 base because the locked
PyTorch environment carries CUDA 13 user-space dependencies. Do not independently
change the CUDA major in the Dockerfile or PyTorch lock; they are one compatibility
contract. The Compute Engine Deep Learning VM family supplies NVIDIA driver 580,
which is the minimum driver family for CUDA 13.x compatibility.

## Dataset versioning / training seam

Dataset versioning is upstream of GPU training. The published Dataset Artifact
and its `dataset-artifact.json` are the input contract at the seam.

GPU deployment and training must:

1. Require the published `dataset-artifact.json`.
2. Validate that it is readable, non-empty JSON before apply/training.
3. Hash the exact manifest used by the run and preserve that SHA-256 in
   preflight, MLflow lineage, and terminal training evidence.
4. Stage the generation-pinned annotation object selected by Terraform.
5. Preserve the exact manifest with the run evidence.

GPU deployment and training must **not** run `dvc init`, `dvc add`, `dvc repro`,
require a newly generated `dvc.lock`, or manufacture replacement dataset
lineage on the training VM. DVC-related publication/versioning remains an
upstream dataset concern; do not rewrite that workflow incidentally while
changing training deployment.

## GPU Terraform deployment workflow

For any GPU training deployment, do not run `terraform apply` as the first
validation step. Use the deployment preflight harness first.

Required order:

1. Read the canonical Terraform root and variables. Prefer the fixed,
   single-instance configuration; do not add configuration knobs without a
   concrete requirement.
2. Build the canonical training image with
   `scripts/cloud/build_training_image.sh`. Use the resulting digest-pinned
   Artifact Registry reference as Terraform's `training_image`.
3. Run `terraform/preflight/preflight.py` with the exact var file and/or
   `-var` values intended for deployment.
4. Treat every `FAIL` checkpoint as blocking. Do not apply around a failed
   repository-contract, Terraform, plan, network, image, service-account,
   dataset, quota, or artifact-write check.
5. Inspect `preflight-report.txt`, `preflight-report.json`,
   `deployment-plan.json`, and the saved `deployment.tfplan`.
6. Review the saved plan with `terraform show`. The root may manage only the
   disposable training VM. Any unexpected update, replacement, destroy, IAM,
   firewall, subnetwork, router, NAT, or other shared-infrastructure change is
   a stop condition.
7. Use the generated `deployment-manifest.json` to apply through
   `scripts/runs/detection.sh --manifest <path>`. The launcher verifies the
   saved plan SHA-256 before applying it. Never regenerate a plan between
   preflight/review and apply.
8. Follow the launcher's checkpoint output and retained startup log. Before
   training, VM startup must pass Local SSD mounting, host Docker/gcloud/NVIDIA
   runtime checks, Artifact Registry Docker authentication, training-image
   pull, Dataset Artifact verification/staging, manifest parse/hash, and CUDA
   visibility from inside the actual training image.
9. Treat `training-evidence.json` as the terminal success/failure record. A VM
   reaching `RUNNING` is not evidence that training succeeded.

`scripts/cloud_preflight.py` remains available as a diagnostic tool for an
already-running VM, but it is not a second required gate in the automatic
startup path. The startup script itself owns the pre-training runtime gates.

The deployment preflight is intentionally read-mostly. Its only cloud mutation
is a reversible write/delete probe under the run artifact prefix. Use
`--skip-write-probe` only when read-only validation is explicitly required and
record the reduced coverage.

### Required checkpoint reporting

Preflight and runtime output must preserve major checkpoints rather than
returning only a final exit code. At minimum report:

- local Terraform/gcloud tooling and active authentication;
- canonical repository training-path checks;
- Terraform formatting, initialization, and validation;
- saved-plan creation and machine-readable plan inspection;
- the single-VM plan contract and absence of destructive/shared-infrastructure
  changes;
- project, zone, machine type, GPU type, auto-mode VPC, service account, boot
  image family, and digest-pinned training image availability;
- readable/valid `dataset-artifact.json`, its SHA-256, image prefix, and pinned
  annotation generation;
- relevant CPU/GPU/external-IP/Local-SSD quota information when exposed;
- artifact-prefix writeability unless explicitly skipped;
- creation of the hash-pinned deployment manifest;
- host Docker and NVIDIA-driver visibility after VM creation;
- successful Artifact Registry Docker authentication before image pull;
- CUDA visibility and CUDA runtime version from inside the training image;
- a final PASS/FAIL summary with the last completed checkpoint.

Keep the generated reports and manifest when diagnosing a failed deployment.
They are the primary record of where provisioning stopped; compare them across
retries instead of repeatedly changing Terraform based only on the final error.
