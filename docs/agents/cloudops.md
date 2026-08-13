# Cloud Operations

This is the canonical agent reference for cloud-service configuration, identity,
and lifecycle.

Use this guide for cloud identity, image builds, VM operations, or cloud
training operations. For Terraform modules, state, plans, and lifecycle
ownership, see [Terraform](terraform.md). See [Data and ingestion](data.md) for
dataset bucket boundaries and publication layout. Cloud operation entrypoints live in
[`scripts/cloud/`](../../scripts/cloud/). Scripts for kicking off cloud runs live
in [`scripts/runs/`](../../scripts/runs/).

## Required capabilities

Before resuming Google Cloud delivery work, install or load the official Google
Cloud capability set: the `google-cloud-storage` Codex plugin plus the `gcloud`
and `google-cloud-recipe-auth` skills. Remove this note once the required
capabilities are available in the standard agent environment.

## Cloud identity

Load `.env.local` only into the invoking process. Do not print, commit, or copy
its values into Terraform variables, plans, logs, or documentation. Cloud
operations require authenticated Application Default Credentials or an
equivalent `gcloud` identity with the required IAM roles; `GCP_API_KEY` is not
an identity credential for Terraform or Compute Engine.

## Cloud Jobs

Data and model flows are independent and may be composed in the same Cloud Job.
The script uses the local Run Recipe to resolve their configured folder and
model names.

Local preparation does not prove remote cloud state. An explicit cloud
operation queries that state, and cloud operations are idempotent: they do not
re-download or recreate an existing input. The workflow may suppress an exact
duplicate run only when a previous run is known to have completed successfully.

A Run Recipe names the model and data that will be used for training. When
either is absent from its Google Storage bucket, the script will acquire it
through its specific workflow.

Before creating or publishing a Dataset, the script will check the remote
folder named by the configured Dataset for `dvc.lock`. A missing
local discovery result or explicit local path is not evidence that the resource
is absent and will not block the Cloud Job.

Before creating a Model Source Adapter, the script will check for the model
named by the Run Recipe.

For every Cloud Job, the script will create a new VM, execute the assigned
Cloud Job, save its outputs while the VM is active, and remove the VM once no
Cloud Job is running. VM creation is not completion, and no idle VM is
retained.

MLflow creates its SQLite database at runtime on the VM. At the end of the
Cloud Job, the startup script uploads that database, the other MLflow outputs,
and best-performing model weights (Model Artifact) to the operational Google
Storage bucket, not the data-specific bucket, before the VM is removed.

## Cloud verification status

You must NOT declare that a workflow status of "has not been validated" as a
blocker. It is a self blocking action. The correct action is to suggest or
initiate verification first by referencing the documentation, then by running
the workflow on the appropriate service. After referencing the documentation,
change the state to "Ready for Cloud Verification".
## Image build flow and operations

`deployment configuration -> image operations script -> Cloud Build -> base
image -> training image -> Artifact Registry`

Cloud Build image construction is distinct from GPU model training. A successful
training-image push and its immutable digest are prerequisites for image-dependent
training operations.

[`scripts/cloud/image_operations.sh`](../../scripts/cloud/image_operations.sh) reads
deployment substitutions and submits the image build to Cloud Build. The Cloud
Build configuration builds and pushes the base image, then builds and pushes the
training image after the base image is available; its `images` field records both
published images. The `base -> training` image graph supplies PyTorch/CUDA before
adding the project; [`deploy/compose.yaml`](../../deploy/compose.yaml) reuses the
base image locally. [`scripts/cloud/stage_model.sh`](../../scripts/cloud/stage_model.sh)
stages an eligible pretrained model to Cloud Storage.

[`deploy/cloudbuild.dvc-image.yaml`](../../deploy/cloudbuild.dvc-image.yaml)
builds the independent Python-only DVC publication image. It contains DVC-GCS
and the Cloud Storage Python client, but not PyTorch/CUDA, FiftyOne, `uv`, or
the Cloud Storage CLI. [`deploy/cloudbuild.coco-acquire-image.yaml`](../../deploy/cloudbuild.coco-acquire-image.yaml)
builds the separate COCO/FiftyOne/MongoDB acquisition image. Source-specific
acquisition and source-agnostic publication run as distinct steps in
[`deploy/cloudbuild.prepare.yaml`](../../deploy/cloudbuild.prepare.yaml); do
not use a PyTorch/CUDA training image for either responsibility.
