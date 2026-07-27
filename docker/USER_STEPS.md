# Docker image setup

This document covers reusable local image builds. Terraform owns the empirical
Docker/GCE smoke and VM lifecycle; see [Product Scope](../docs/planning/product-scope.md).

## Configure and run cloud operations

Edit [`deploy/cloudbuild.yaml`](../deploy/cloudbuild.yaml) to select the GCP
project, Artifact Registry repository, and image tags. The Compose graph builds
the PyTorch/CUDA `base` image once and then builds the `training` image from it.
Docker reuses the base image and layers on subsequent builds.

```bash
docker compose --file deploy/compose.yaml build
```

For Cloud Build, run `uv run python scripts/cloud/run.py build`. It publishes
the base image to Artifact Registry and uses that image as the remote cache for
future builds; this is necessary because Cloud Build workers do not retain local
Docker layers between builds.

---
