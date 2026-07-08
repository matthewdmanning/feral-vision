# Feral Segmentor — Project Requirements

## 1. Purpose

Detect and segment feral cats in images captured on mobile devices. Output pixel-level instance masks suitable for downstream tracking, population monitoring, or trap-neuter-return (TNR) programme support.

---

## 2. Functional Requirements

### 2.1 Data Acquisition

| ID | Requirement |
|----|-------------|
| D-01 | System shall download COCO train2017 images belonging to the `animal` supercategory (10 classes: bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe). |
| D-02 | Download shall be idempotent — already-present files shall be skipped. |
| D-03 | Filtered instance annotations shall be saved as `instances_train2017_animals.json`. |
| D-04 | System shall convert COCO polygon segmentation annotations to YOLO segmentation format (normalised flat polygon `.txt` files, one per image). |
| D-05 | Train/val split shall be static, seeded (seed=42), configurable ratio, and stored in GCS before training begins. |
| D-06 | Data source, root path, image size, val split ratio, and per-class similarity weights shall all be configurable via Hydra without code changes. |

### 2.2 Augmentation

| ID | Requirement |
|----|-------------|
| A-01 | Augmentation pipeline shall be composable via a fluent chain (each transform wraps an inner transform). |
| A-02 | Supported transforms: All Albumentations. |
| A-03 | Active augmentation chain shall be specified in Hydra config (`augmentation.ops`). |
| A-04 | Augmented images shall be written to `data/augmented/` with the chain name appended to the filename stem. |

### 2.3 Model

| ID | Requirement |
|----|-------------|
| M-01 | Student model shall be YOLO11n-seg (nano segmentation head) — optimised for mobile inference. |
| M-02 | Teacher model shall be YOLO11x-seg (extra-large) for knowledge distillation. |
| M-03 | Model weights shall be fetchable from local path, remote endpoint, or a Pytorch script entrypoint; source is specified in Hydra config. |

### 2.4 Training

| ID | Requirement |
|----|-------------|
| T-01 | All hyperparameters (epochs, lr, batch size, optimizer, scheduler, weight decay, momentum) shall be Hydra-configurable. |
| T-02 | Best weights checkpoint shall be saved whenever tracked loss improves. |
| T-03 | Training metrics (train loss, val loss per epoch) shall be logged to MLflow. |

### 2.5 Infrastructure

| ID | Requirement |
|----|-------------|
| I-01 | Training shall run in a Docker container on a GCE T4 GPU instance. |
| I-02 | Base image: `nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04`. |
| I-03 | Container image shall be stored in Google Artifact Registry. |
| I-04 | GCS authentication shall use Workload Identity (instance service account) — no key files. |
| I-05 | Dataset shall be synced from GCS to an attached SSD (`/data/`) before training starts. |
| I-06 | Training outputs (YOLO runs, checkpoints) shall be pushed to GCS on completion. |
| I-07 | MLflow tracking server shall run as a sidecar process on the same instance, with artifacts stored in GCS. |
| I-08 | All GCS bucket names, project IDs, and instance configuration shall remain outside the Docker image (supplied via environment variables or gcloud CLI at runtime). |

---

## 3. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NF-01 | No magic numbers in logic or config schema. |
| NF-02 | Hydra `base.yaml` and `default.yaml` files shall not be modified; experiment variants shall use named yaml copies. |
| NF-03 | Data download and augmentation stages shall be idempotent and re-runnable. |
| NF-04 | Training loop shall function without a running MLflow server (metric logging silently skipped if no active run). |
| NF-05 | Python == 3.12, PyTorch ≥ 2.12, CUDA 12.1. |

---

## 4. Out of Scope

- Real-time video inference pipeline
- Active learning / human-in-the-loop labelling
- Multi-GPU / distributed training
- Model serving API

---

## 5. Key Configuration Files

| File | Purpose |
|------|---------|
| `conf/data/coco_train2017.yaml` | COCO dataset source, paths, class similarity weights |
| `conf/train/default.yaml` | Hyperparameters |
| `conf/model/default.yaml` | Model source, architecture dims |
| `conf/augmentation/default.yaml` | Augmentation chain ops |
| `docker/Dockerfile` | Container definition |
| `docker/entrypoint.sh` | GCS sync → train → push pipeline |
| `docker/USER_STEPS.md` | User action checklist for GCS + Artifact Registry + GPU setup |
