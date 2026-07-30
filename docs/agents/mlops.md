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

The Terraform startup restores a previously archived bounded COCO export from
Cloud Storage to VM SSD before downloading. A first run downloads the subset;
normal shutdown archives it for later VM runs.

## Cloud Dataset Artifacts

### Storage structure

```text
Cloud Storage
├── dataset-only bucket                 # one bucket per environment
│   └── datasets/<dataset>/<artifact>/
│       ├── images/
│       ├── annotations/
│       ├── dataset-artifact.json
│       └── <dataset>.dvc
└── general storage
    ├── Terraform state + Cloud Build staging
    ├── MLflow artifacts
    └── non-dataset operational assets
```

The dataset-only bucket is the source for Dataset Artifacts and is the only
bucket whose object versions DVC pins. It has Object Versioning, dataset-specific
lifecycle rules, and least-privilege access for the Cloud Build publisher,
DVC-repository automation, and training readers. General storage must not be a
source for a Dataset Artifact. Keep Terraform state in a dedicated protected
operations bucket with Cloud Build staging when their prefixes have separate,
least-privilege IAM conditions; both remain separate from datasets.

Cloud Build publishes prepared data to a versioned Cloud Storage prefix. A
separate DVC-scoped Git repository owns Dataset Artifact pointers and manifests;
it contains no dataset blobs and is independent of the application repository.
After publication, its automation creates or updates a tracker with
`dvc import-url --version-aware` against the GCS prefix and commits the tracker
and `dataset-artifact.json` together through the data repository's review
workflow. Object Versioning must be enabled on the source bucket before this
workflow is used.

The resulting tracker records the GCS object generations. Training consumes the
selected tracker and staged data, and records the data-repository commit and
tracker digest in its run manifest and MLflow lineage. A new cloud version is
adopted only by updating that tracker (for a selected version, `dvc update --rev`
may be used) and reviewing the corresponding data-repository change. Do not use
`dvc add --no-scm` in the application build as a substitute for this provenance
boundary, and do not run DVC in the training container.
