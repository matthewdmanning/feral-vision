# Configuration

## Purpose

`conf/` holds version-controlled model, data, training, inference, tracking, and
augmentation values. Python schemas own field contracts; YAML files own the
values selected by the executable Run Recipe.

## Canonical training recipe

There is exactly one complete training Run Recipe:

- [`runs/detection.yaml`](runs/detection.yaml)

Local training, container-image validation, and the GPU deployment all compose
that same recipe. Deployment may override runtime locations such as
`data.root`, but it must not select a different Run Recipe.

Component YAML files under `data/`, `model/`, `train/`, `inference/`,
`tracking/`, and `augmentation/` remain implementation components of that
recipe; they are not additional deployment configurations.

Cloud infrastructure and image-build inputs are intentionally not represented
as Hydra configuration. GPU infrastructure is owned by
`terraform/runs/detection/`, and the canonical training image is built through
`deploy/Dockerfile.gcp` and `deploy/cloudbuild.training-image.yaml`.
