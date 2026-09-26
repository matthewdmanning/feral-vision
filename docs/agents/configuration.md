# Configuration

Use this guide when changing Hydra or model configuration.

## Training recipe policy

`conf/runs/detection.yaml` is the only complete training Run Recipe. Local
training, image validation, and GPU deployment must compose it. Do not create a
second Run Recipe for a deployment, experiment, environment, or one-off run.
Use Hydra overrides or change the canonical component configuration when a
value genuinely needs to vary.

Component YAML files under `data/`, `model/`, `train/`, `inference/`,
`tracking/`, and `augmentation/` own concern-specific values; they are not
complete training configurations by themselves.

A required model architecture `location` must remain non-null so model
construction is reproducible.

## Deployment boundary

Hydra owns training behavior. Terraform and image-build configuration do not
belong in Hydra. GPU infrastructure is owned by `terraform/runs/detection/` and
the training image is owned by `deploy/Dockerfile.gcp` plus
`deploy/cloudbuild.training-image.yaml`.

The selected Dataset Artifact is also not re-versioned by Hydra or the GPU
runtime. Its upstream `dataset-artifact.json` crosses into training as the
provenance contract.
