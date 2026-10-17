# Configuration

Use this guide when changing Hydra or model configuration.

## Training configuration selection

The generic container runner accepts the user's config directory and config
name and uses that Hydra configuration as written. It supplies no overrides.
`feral-vision/conf/` is a library of configurations previously tried, not a
single mandatory experiment. Use `src/sightkit_learn/config/` as the contract;
Hydra composition produces an OmegaConf `DictConfig`.

The existing detection deployment selects `runs/detection`; that describes its
current wiring and does not constrain the generic training template. See the
[training guide](../guide/training.rst) for configuration and output handling.

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
belong in Hydra. GPU infrastructure is owned by `feral-vision/terraform/runs/detection/` and
the training image is owned by `feral-vision/deploy/Dockerfile.gcp` plus
`feral-vision/deploy/cloudbuild.training-image.yaml`.

Assume the selected data, model, DVC and config files already exist in Cloud
Storage. The generic training script does not version or publish inputs. The
existing detection deployment separately consumes its upstream
`dataset-artifact.json` provenance record.
