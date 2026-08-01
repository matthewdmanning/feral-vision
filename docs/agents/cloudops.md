# Cloud Operations

This is the canonical agent reference for cloud-service configuration, identity,
and lifecycle.

Use this guide for Terraform, cloud identity, VM lifecycle, image builds, or
cloud training operations.

## Cloud Folder Layoout

```text
Cloud Storage
├── dataset-only bucket                 # one bucket per environment

└── general storage
    ├── Terraform state + Cloud Build staging
    ├── MLflow artifacts
    └── non-dataset operational assets
```

## Terraform

Terraform owns cloud-resource configuration and lifecycle; Hydra configures
workloads; operational scripts use provisioned services. Load `.env.local` only
into the invoking process. Do not print, commit, or copy its values into plans,
logs, or documentation. Cloud operations require ADC or equivalent `gcloud`
identity, not `GCP_API_KEY`.

The current GCP example declares storage, GPU VM, service account, and access
rules in [`terraform/`](../../terraform/). `deploy/cloudbuild.yaml` declares
image-build inputs; `scripts/cloud/run.py` dispatches `build` and `push`.

The `base -> training` image graph supplies PyTorch/CUDA before adding the
project. `deploy/compose.yaml` reuses the base image locally.
`deploy/cloudbuild.build.yaml` publishes that base image for remote build
caching, then publishes the final training image. `stage_model.sh` stages an
eligible pretrained model to Cloud Storage.

## Cloud services and operations

Terraform owns the configuration and lifecycle of cloud services: storage,
registries, compute, network, identity, and access policy. Hydra configures
workloads; operational scripts use the provisioned services without recreating
or redefining them.

Local cloud credential settings are kept in this checkout's `.env.local`. Load
that file only into the invoking process; never print, commit, or copy its
values into Terraform variables, plans, logs, or documentation. A `GCP_API_KEY`
is not an identity credential for Terraform or Compute Engine: cloud operations
require authenticated Application Default Credentials or an equivalent
`gcloud` identity with the required IAM roles.

The current GCP example references its existing Cloud Storage archive bucket
and declares the private GPU VM, Cloud NAT egress, service account, and access
rules in [`terraform/`](../../terraform/). The cloud-smoke
configuration declares image-build project and Artifact Registry inputs in
[`deploy/cloudbuild.yaml`](../../deploy/cloudbuild.yaml). [`scripts/cloud/run.py`](../../scripts/cloud/run.py)
dispatches image `build` and `push` operations. The `base -> training` image graph
supplies PyTorch/CUDA before adding the project; `deploy/compose.yaml` reuses the
base image locally. [`deploy/cloudbuild.build.yaml`](../../deploy/cloudbuild.build.yaml)
publishes the base image to Artifact Registry for remote build caching and then
publishes the final training image. [`stage_model.sh`](../../scripts/cloud/stage_model.sh)
stages an eligible pretrained model to Cloud Storage.

[`deploy/cloudbuild.dvc-image.yaml`](../../deploy/cloudbuild.dvc-image.yaml)
builds the independent Python-only DVC publication image. It contains DVC-GCS
and the Cloud Storage Python client, but not PyTorch/CUDA, FiftyOne, `uv`, or
the Cloud Storage CLI. `deploy/cloudbuild.coco-acquire-image.yaml` builds the
separate COCO/FiftyOne/MongoDB acquisition image. Source-specific acquisition and
source-agnostic publication run as distinct steps in
`deploy/cloudbuild.prepare.yaml`; do not use a PyTorch/CUDA training image for
either responsibility.
