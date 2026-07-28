# MLOps boundaries

Use this guide when a task spans DVC, Hydra, MLflow, source code, or the model
registry.

This is the canonical agent reference for cloud-service configuration, identity,
and lifecycle. The execution data-to-model flow is in [Program Flow](program-flow.md).

Scope strictly to the task at hand. See
[the tooling boundaries](program-flow.md#tool-ownership)
for DVC, Hydra, MLflow, source-code, and model-registry ownership. Never log
raw data directories to MLflow; use a Dataset Artifact for Data Lineage.

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

The current GCP example declares its Cloud Storage bucket, GPU VM, service
account, and access rules in [`terraform/`](../../terraform/). The cloud-smoke
configuration declares image-build project and Artifact Registry inputs in
[`deploy/cloudbuild.yaml`](../../deploy/cloudbuild.yaml). [`scripts/cloud/run.py`](../../scripts/cloud/run.py)
dispatches image `build` and `push` operations. The `base -> training` image graph
supplies PyTorch/CUDA before adding the project; `deploy/compose.yaml` reuses the
base image locally. [`deploy/cloudbuild.build.yaml`](../../deploy/cloudbuild.build.yaml)
publishes the base image to Artifact Registry for remote build caching and then
publishes the final training image. [`stage_model.sh`](../../scripts/cloud/stage_model.sh)
stages an eligible pretrained model to Cloud Storage.
