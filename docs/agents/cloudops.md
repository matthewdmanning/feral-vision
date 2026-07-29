# Cloud Operations

Use this guide for Terraform, cloud identity, VM lifecycle, image builds, or
cloud training operations.

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
