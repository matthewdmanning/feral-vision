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
