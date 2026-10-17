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

Common training tasks, loss execution, prepared DataLoaders/collators, monitors,
and model-publication settings are declared in `config/schema.py` and selected
through Hydra. Standard task support must not require editing Python or writing
a callback. See [Hydra task execution](training.md#hydra-selects-common-task-execution)
and the [training guide](../guide/training.rst) for the supported fields and
native provider contracts. `model.architecture.kwargs` carries native
constructor/loading options; `tracking.serialization_format`, optional input
examples, and signatures control MLflow publication.

Inference uses the registered `InferenceConfig` schema. Set
`inference.model_uri`, then configure device, native load/forward options,
calling convention, and optional processors through Hydra. See the
[inference guide](../guide/inference.rst). A model URI is required only when
building inference; training recipes can leave it unset. Inference reads the
configured tracking URI without starting an experiment run.
`inference.dataloader` and optional `collate_fn` configure native prepared
dataset batches. `input_selector` and `target_selector` are Hydra callable
targets for labeled inference; paired batches need no selector configuration.
Training and inference share loader construction without imposing a custom
Dataset/Annotation representation. Select inference sampling/transforms
explicitly for the held-out Dataset.

## Deployment boundary

Hydra owns training behavior. Terraform and image-build configuration do not
belong in Hydra. GPU infrastructure is owned by `terraform/runs/detection/` and
the training image is owned by `deploy/Dockerfile.gcp` plus
`deploy/cloudbuild.training-image.yaml`.

The selected Dataset Artifact is also not re-versioned by Hydra or the GPU
runtime. Its upstream `dataset-artifact.json` crosses into training as the
provenance record.
