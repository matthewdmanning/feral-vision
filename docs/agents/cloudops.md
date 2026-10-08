# Cloud Operations

This is the canonical agent reference for cloud-service configuration, identity,
image builds, VM operations, and GPU training operations. For Terraform state,
plans, and lifecycle ownership, see [Terraform](terraform.md). See
[Data and ingestion](data.md) for dataset publication details.

## Cloud identity

Load `.env.local` only into the invoking process. Do not print, commit, or copy
its values into Terraform variables, plans, logs, or documentation. Cloud
operations require authenticated Application Default Credentials or an
equivalent `gcloud` identity with the required IAM roles; `GCP_API_KEY` is not
an identity credential for Terraform or Compute Engine.

## Canonical GPU training path

There is one supported GPU training path:

~~~text
conf/runs/detection.yaml
        |
deploy/Dockerfile.gcp
        |
deploy/cloudbuild.training-image.yaml
        |
scripts/cloud/build_training_image.sh
        |
digest-pinned Artifact Registry image
        |
terraform/preflight/preflight.py
        |
terraform/runs/detection/
        |
scripts/runs/detection.sh
~~~

Do not add a run-specific training Dockerfile, duplicate Run Recipe, alternate
image-build dispatcher, or sibling Terraform root for the same one-VM training
job. The deployment preflight fails if any of them appears.

## Dataset Artifact boundary

Cloud data operations and GPU training share one explicit boundary: the
published Dataset Artifact. Training derives all input paths from one
`dataset_artifact_prefix`; it must not search for images or annotations across
bucket prefixes.

The training-facing layout is:

~~~folder
gs://<dataset-bucket>/datasets/<source>/<split>/<artifact>/
├── payload/
│   ├── images/
│   └── annotations/
└── dataset-artifact.json
~~~

Upstream publication may maintain additional DVC metadata. That is not part of
the GPU runtime. Do not remove or redesign upstream DVC behavior while
working on GPU deployment without an explicit task to do so.

For GPU training, `dataset-artifact.json` is the provenance record. Preflight
reads and parses it, records its SHA-256, and verifies the selected retained
annotation generation. The VM then stages the payload and exact manifest onto
Local SSD, re-hashes the manifest, and passes that hash into the training
container. MLflow and terminal evidence record the same hash.

The GPU VM must **not** initialize DVC, run `dvc add`/`dvc repro`, require a
newly generated `dvc.lock`, or manufacture replacement dataset lineage. A
failure at the data-versioning/training seam is a malformed/missing published
artifact, a changed manifest hash, or a missing pinned object generation.

## Training image

The canonical image is [`deploy/Dockerfile.gcp`](../../deploy/Dockerfile.gcp).
It starts from a digest-pinned NVIDIA CUDA 13 base and installs the locked
project environment. The lock currently pins PyTorch 2.12.1 with CUDA 13
user-space dependencies, including cuDNN; do not add a second cuDNN runtime to
the base image. The image also contains `gcloud` and uses
[`scripts/runs/container_train.sh`](../../scripts/runs/container_train.sh) as
its entrypoint.

The CUDA major in the Dockerfile and the CUDA major in the PyTorch lock must
match. Change both together. The preflight
fails if a second training Dockerfile, Run Recipe, or container entrypoint
appears.

The Compute Engine host uses Google's current PyTorch 2.9 / CUDA 12.9 Deep
Learning VM family with NVIDIA driver 580. CUDA 13 applications are supported
on driver family 580 through NVIDIA CUDA minor-version compatibility. Startup
must still prove the actual host driver and in-container CUDA visibility before
training begins; documentation is not a substitute for that runtime gate.

### Check for an existing image first

**STOP. Before you write "the image is not built", and before you start a build,
run the check.** Earlier agents built the image, forgot it, and claimed it did
not exist. Artifact Registry is the only source of truth; memory, notes, and
local files are not.

```bash
scripts/cloud/check_training_image.sh \
  --project cs-poc-kewg0kffb7uwobgq1rex2af --region us-east4 \
  --repository feral-docker --image feral-vision-gcp
```

The command is read-only. It lists every push of the image, compares the newest
push with the last commit that touched a build input (`deploy/Dockerfile.gcp`,
the Cloud Build file, `container_train.sh`, `src/`, `conf/`, `pyproject.toml`,
`uv.lock`), and prints one of three results:

| Result | Meaning | Action |
| --- | --- | --- |
| exit 1, `NO IMAGE FOUND` | No push exists. | Build. |
| exit 0, `STALE` | An image exists but a build input changed after it. | Rebuild. |
| exit 0, `CURRENT` | An image exists and no committed input changed. | Do not rebuild. Use the printed digest-pinned reference as `training_image`. |

The check does not see uncommitted changes. Run `git status` before you trust
`CURRENT`. Run the check again after every build.

Build the image only through
[`scripts/cloud/build_training_image.sh`](../../scripts/cloud/build_training_image.sh),
which submits [`deploy/cloudbuild.training-image.yaml`](../../deploy/cloudbuild.training-image.yaml).
Cloud Build must complete the image check before the image is pushed.
The build script resolves the pushed image digest and prints the digest-pinned
reference consumed by Terraform.

Cloud Build image construction is distinct from GPU training. A successful
push plus an immutable digest is a prerequisite; a mutable tag is never a
Terraform training input.

Dataset acquisition/publication images such as `Dockerfile.dvc` or
`Dockerfile.coco-acquire` are separate upstream responsibilities. Do not use the
GPU training image for those jobs, and do not infer that their DVC behavior
belongs in the GPU runtime.

## Artifact Registry pull authentication

A VM service account with Artifact Registry Reader permission and
`cloud-platform` scope authorizes access, but a Docker client must still be
configured to authenticate to the registry. Before the first `docker pull`, VM
startup derives the registry hostname from the digest-pinned image reference
and runs `gcloud auth configure-docker <registry-host> --quiet`.

Do not remove this as redundant IAM setup. IAM/scopes answer whether the VM may
read the image; Docker credential-helper configuration answers how the Docker
client presents those short-lived credentials.

## Deployment and runtime checkpoints

Run [`terraform/preflight/preflight.py`](../../terraform/preflight/preflight.py)
before every GPU apply. It validates the canonical repository path, Terraform,
the saved plan, GCP prerequisites, Dataset Artifact manifest/hash, quotas, and
run-artifact writeability. A passing run emits `deployment-manifest.json` with
the SHA-256 of the exact saved plan.

Apply through [`scripts/runs/detection.sh`](../../scripts/runs/detection.sh).
The launcher rejects a modified plan, records Terraform outputs, confirms the
instance reached `RUNNING`, collects serial output, and waits for terminal
`training-evidence.json`.

VM startup logs explicit checkpoints for Local SSD mount, host Docker/gcloud/
NVIDIA runtime visibility, Artifact Registry authentication, image pull,
Dataset Artifact verification/staging, manifest validation, in-container CUDA
visibility, and training. VM creation or `RUNNING` status is not training
success.

The VM remains Terraform-owned after container exit. Removal requires a
separately reviewed Terraform destroy plan.

[`scripts/cloud_preflight.py`](../../scripts/cloud_preflight.py) is a
diagnostic tool for an already-running VM. It is not a second required gate in
the automatic startup path, because the startup script owns the pre-training
runtime gates.

## MLflow evidence

The resolved training config is logged to MLflow. Dataset lineage is the exact
`dataset-artifact.json` used by the run plus its SHA-256, not a GPU-generated
DVC tracker. The startup script also preserves the exact manifest and terminal
training evidence under the operational run artifact prefix.

A local SQLite tracking URI is allowed for the one-VM job. If a remote tracking
service is configured, use an approved HTTPS endpoint. MLflow artifacts belong
in the operational artifact location, never the dataset-only bucket.

## Cloud verification status

Do not treat “has not been validated” as a permanent blocker. Run the documented
preflight or service verification and report the concrete failed checkpoint.
Do not weaken or bypass a blocking check merely to advance deployment.
