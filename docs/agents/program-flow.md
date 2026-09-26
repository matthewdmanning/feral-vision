# Program Flow

## Training deployment

```mermaid
flowchart TB
    upstream["Upstream dataset publication / versioning"]
    dataset["Published Dataset Artifact\npayload + dataset-artifact.json"]
    recipe["conf/runs/detection.yaml"]
    dockerfile["deploy/Dockerfile.gcp\nNVIDIA CUDA 13 base"]
    cloudbuild["deploy/cloudbuild.training-image.yaml"]
    registry["Artifact Registry\ndigest-pinned training image"]
    preflight["terraform/preflight/preflight.py"]
    plan["Reviewed saved Terraform plan\n+ deployment-manifest.json"]
    terraform["terraform/runs/detection/"]
    vm["Single T4 VM + NVMe Local SSD\nNVIDIA driver 580"]
    auth["Docker runtime + Artifact Registry auth"]
    staged["Staged Dataset Artifact\nmanifest SHA verified"]
    train["scripts/runs/container_train.sh\nCUDA visibility verified"]
    mlflow["MLflow run + Dataset Artifact lineage"]
    evidence["training-evidence.json\n+ exact dataset-artifact.json"]

    upstream --> dataset
    dockerfile --> cloudbuild --> registry
    recipe --> cloudbuild
    dataset --> preflight
    registry --> preflight
    terraform --> preflight --> plan
    plan --> terraform --> vm --> auth
    dataset --> vm --> staged --> train
    registry --> auth --> train
    recipe --> train
    train --> mlflow
    train --> evidence
    staged --> mlflow
    staged --> evidence
```

Dataset versioning is upstream of GPU training. DVC may participate in the
publication workflow, but the GPU VM consumes the already-published Dataset
Artifact. The GPU runtime does not run DVC or generate a replacement lockfile.
`dataset-artifact.json` is the provenance contract across the seam.

The training image has one build path: `deploy/Dockerfile.gcp` through
`deploy/cloudbuild.training-image.yaml`. The digest-pinned NVIDIA CUDA 13 base
matches the CUDA major used by the locked PyTorch runtime; PyTorch supplies its
own locked CUDA/cuDNN user-space dependencies. There is no intermediate Feral
Vision base image and no run-specific training image.

Terraform owns the disposable VM lifecycle. Preflight validates the exact
saved plan and records its SHA-256 together with the training-image digest and
Dataset Artifact manifest SHA-256. `scripts/runs/detection.sh` applies only that
reviewed plan and waits for terminal training evidence.

After VM creation, startup proves host Docker/NVIDIA tooling, configures Docker
for Artifact Registry using the VM identity, pulls the exact digest, verifies
the Dataset Artifact, and confirms CUDA from inside the real training image.
VM creation or RUNNING status is not training success.

[Cloud Operations](cloudops.md) · [Terraform](terraform.md) ·
[Configuration](configuration.md) · [Training guide](../guide/training.rst)
