# MLOps boundaries

Use this guide when a task spans DVC, Hydra, MLflow, source code, or the model
registry.

Scope strictly to the task at hand. See
[the tooling boundaries](../architecture/program-flow.md#7-tooling-boundaries)
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

The initial Cloud Storage resource for the manual smoke is declared in
[`terraform/`](../../terraform/). It accepts the GCP project and bucket name as
inputs and deliberately retains local Terraform state for this first smoke;
do not treat that state as MLflow or dataset lineage.

The current GCP example declares its Cloud Storage bucket, GPU VM, service
account, and access rules in [`terraform/`](../../terraform/). It uses the
GPU-enabled PyTorch Deep Learning VM image family and installs the NVIDIA driver
on first boot. Terraform-managed startup and shutdown metadata invoke the
CUDA-enabled PyTorch training image and archive the selected COCO export before
normal VM shutdown.
The cloud-smoke configuration declares only the image-build project and Artifact
Registry inputs in [`deploy/cloudbuild.yaml`](../../deploy/cloudbuild.yaml).
[`scripts/cloud/run.py`](../../scripts/cloud/run.py) dispatches image `build` and
`push` shell operations. [`deploy/cloudbuild.build.yaml`](../../deploy/cloudbuild.build.yaml)
builds the PyTorch base and final training image, then publishes the latter to
Artifact Registry;
[`stage_model.sh`](../../scripts/cloud/stage_model.sh)
stages an eligible pretrained model to Cloud Storage.

See the [program flow](../architecture/program-flow.md) for the data/training boundary.
