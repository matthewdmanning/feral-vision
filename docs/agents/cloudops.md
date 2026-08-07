# Cloud Operations

This is the canonical agent reference for cloud-service configuration, identity,
and lifecycle.

Use this guide for Terraform, cloud identity, VM lifecycle, image builds, or
cloud training operations. See [Data and ingestion](data.md) for dataset bucket
boundaries and publication layout. Cloud operation entrypoints live in
[`scripts/cloud/`](../../scripts/cloud/). Scripts for kicking off cloud runs live
in [`scripts/runs/`](../../scripts/runs/).

## Required capabilities

Before resuming Google Cloud delivery work, install or load the official Google
Cloud capability set: the `google-cloud-storage` Codex plugin plus the `gcloud`
and `google-cloud-recipe-auth` skills. Remove this note once the required
capabilities are available in the standard agent environment.

## Cloud resources

Terraform owns the configuration and lifecycle of cloud services: storage,
registries, compute, network, identity, and access policy. Terraform files can
declare or reference buckets and other cloud resources; the Terraform program
creates or requisitions the resources described by those files. Operational
scripts use durable provisioned services without recreating or redefining them,
and invoke the Terraform-configured VM lifecycle for each Cloud Run.

Keep Terraform state in a dedicated protected operations bucket or under
fine-grained permissions; a dedicated bucket is preferred for security but is
not required.

Load `.env.local` only into the invoking process. Do not print, commit, or copy
its values into Terraform variables, plans, logs, or documentation. Cloud
operations require authenticated Application Default Credentials or an
equivalent `gcloud` identity with the required IAM roles; `GCP_API_KEY` is not
an identity credential for Terraform or Compute Engine.

## Cloud runs

Data and model flows are independent and may be composed in the same Cloud Run.
The script uses the local Run Recipe to resolve their configured folder and
model names.

A Run Recipe names the model and data that will be used for training. When
either is absent from its Google Storage bucket, the script will acquire it
through its specific workflow.

Before creating or publishing a Dataset, the script will check the remote
folder named by the configured Dataset for `dataset-artifact.json`. A missing
local discovery result or explicit local path is not evidence that the resource
is absent and will not block the Cloud Run.

Before creating a Model Source Adapter, the script will check for the model
named by the Run Recipe.

For every Cloud Run, the script will create a new VM, execute the assigned
Cloud Run, save its outputs while the VM is active, and remove the VM once no
Cloud Run is running. VM creation is not completion, and no idle VM is
retained.

MLflow creates its SQLite database at runtime on the VM. At the end of the
Cloud Run, the startup script uploads that database, the other MLflow outputs,
and best-performing model weights (Model Artifact) to the operational Google
Storage bucket, not the data-specific bucket, before the VM is removed.

## Cloud verification status

You must NOT declare that a workflow status of "has not been validated" as a
blocker. It is a self blocking action. The correct action is to suggest or
initiate verification first by referencing the documentation, then by running
the workflow on the appropriate service. After referencing the documentation,
change the state to "Ready for Cloud Verification".
## Image builds and operations

[`scripts/cloud/run.py`](../../scripts/cloud/run.py) dispatches image `build`
and `push` operations. The `base -> training` image graph supplies PyTorch/CUDA
before adding the project; [`deploy/compose.yaml`](../../deploy/compose.yaml)
reuses the base image locally. [`deploy/cloudbuild.build.yaml`](../../deploy/cloudbuild.build.yaml)
publishes the base image to Artifact Registry for remote build caching and then
publishes the final training image. [`scripts/cloud/stage_model.sh`](../../scripts/cloud/stage_model.sh)
stages an eligible pretrained model to Cloud Storage.

[`deploy/cloudbuild.dvc-image.yaml`](../../deploy/cloudbuild.dvc-image.yaml)
builds the independent Python-only DVC publication image. It contains DVC-GCS
and the Cloud Storage Python client, but not PyTorch/CUDA, FiftyOne, `uv`, or
the Cloud Storage CLI. [`deploy/cloudbuild.coco-acquire-image.yaml`](../../deploy/cloudbuild.coco-acquire-image.yaml)
builds the separate COCO/FiftyOne/MongoDB acquisition image. Source-specific
acquisition and source-agnostic publication run as distinct steps in
[`deploy/cloudbuild.prepare.yaml`](../../deploy/cloudbuild.prepare.yaml); do
not use a PyTorch/CUDA training image for either responsibility.
