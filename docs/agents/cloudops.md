# Cloud Operations

This is the canonical agent reference for cloud-service configuration, identity,
and lifecycle.

Use this guide for Terraform, cloud identity, VM lifecycle, image builds, or
cloud training operations. See [Data and ingestion](data.md) for dataset bucket
boundaries and publication layout. Cloud operation entrypoints live in
[`scripts/cloud/`](../../scripts/cloud/). Scripts for kicking off cloud runs live
in [`scripts/runs/`](../../scripts/runs/).

## Cloud resources

Terraform owns the configuration and lifecycle of cloud services: storage,
registries, compute, network, identity, and access policy. Terraform files can
declare or reference buckets and other cloud resources; the Terraform program
creates or requisitions the resources described by those files. Operational
scripts use provisioned services without recreating or redefining them.

Load `.env.local` only into the invoking process. Do not print, commit, or copy
its values into Terraform variables, plans, logs, or documentation. Cloud
operations require authenticated Application Default Credentials or an
equivalent `gcloud` identity with the required IAM roles; `GCP_API_KEY` is not
an identity credential for Terraform or Compute Engine.

The current GCP example declares storage, the private GPU VM, Cloud NAT egress,
service account, and access rules in [`terraform/`](../../terraform/). The
cloud-smoke configuration declares image-build project and Artifact Registry
inputs in [`deploy/cloudbuild.yaml`](../../deploy/cloudbuild.yaml).

For `first_run_augmented`, the VM startup script creates the MLflow server on
the VM loopback interface at `http://127.0.0.1:5000`. This URI is a runtime
output, not an operator input: the training container uses host networking to
reach it, and startup exports the completed Run Record to the configured
MLflow artifact prefix before the disposable VM is removed.

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

The Dataset Artifact Cloud Build configurations execute as
`feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com`.
Grant that identity `roles/artifactregistry.createOnPushWriter` for the image
publication path; the role includes both create-on-push and artifact-upload
permissions. Do not infer a substitute identity from a default account observed
in a failed build.
