# Inference

The reusable inference submodule loads models published to MLflow and executes
prepared inputs. It belongs to the library described by
[modules.md](../domain/modules.md); no production scripts or configuration paths
are imported into it.

## Loading and configuration

`inference.predictor.build_predictor(cfg)` consumes the structured Hydra
`inference` configuration and optional `tracking.tracking_uri`. It loads once
through the public `mlflow.pytorch.load_model` function. `inference.model_uri`
selects an MLflow artifact path, logged model, registered version, or alias.
The unset default keeps existing training recipe composition valid; inference
requires an explicit model URI.

- `inference.device` selects both loading and input tensor placement.
- `inference.load_kwargs` supplies native loading options, including `dst_path`
  and an explicit `map_location` override. Default map location is the selected
  device, so eager models trained on CUDA can load for CPU inference.
- `inference.call_mode` selects `auto`, `positional`, `args`, or `kwargs`.
- `inference.forward_kwargs` supplies native model-forward options.
- `inference.preprocess` and `inference.postprocess` are optional Hydra targets
  for existing provider/library callables. Native Python containers are passed
  to their constructors. A function awaiting its input uses `_partial_: true`.
- `inference.dataloader` constructs an existing prepared dataset/DataLoader;
  `inference.collate_fn` supplies a collator when the loader does not select one.
- `inference.input_selector` and `inference.target_selector` select the two
  sides of a labeled dataset batch, defaulting to positions zero and one.

MLflow handles URI resolution, registry aliases, artifact retrieval, and model
serialization. Do not replicate those mechanisms or fall back to downloading
another provider model. Rebuilding a predictor resolves an alias again; an
existing predictor keeps its already-loaded model for all of its batches.
Inference does not start an MLflow run or automatically log input images or
prediction artifacts.

## Native execution

`Predictor.predict(inputs)` runs preprocessing, device movement, native forward,
and optional postprocessing under `torch.inference_mode()`. MLflow places eager
models in evaluation mode. Exported models use their captured behavior; a
second `.eval()` call is not made because exported modules can reject it.
MLflow's device restrictions for exported graphs remain its own contract.

Auto calling conventions are explicit:

| Prepared input | Native invocation |
| --- | --- |
| Tensor batch | `model(batch, **forward_kwargs)` |
| Image list, including different image sizes | `model(images, **forward_kwargs)` |
| Keyword mapping, such as HF processor outputs | `model(**inputs, **forward_kwargs)` |
| Positional tuple | `model(*inputs, **forward_kwargs)` |

Explicit call modes handle a model expecting a mapping or tuple as one
positional input, or a list as several arguments. Tensor placement is shared
with training through `utils.to_device`; inference does not import the training
loop. Non-tensor metadata is retained. Prepared inputs must match the selected
model's native preprocessing/padding contract; no image loader, universal
normalization, annotation conversion, or task-specific target inference is
added here.

Without a configured postprocessor, return the exact native output object.
Tensors, semantic dictionaries, instance/pose lists, tuples, and Transformers
ModelOutput objects are not flattened, moved to CPU, converted to NumPy, or
filtered implicitly. Task-specific confidence thresholds, augmentation, and
mask cleanup belong to explicitly configured provider calls/processors. The
existing `threshold`, `tta`, and `min_box_area` values can be referenced there;
they do not impose generic operations on every model's output.

`Predictor.predict_batches(batches)` yields one result per prepared batch and
reuses the loaded model without buffering the stream. It does not guess which
parts of a batch are labels or remove them automatically.

## Dataset batches

`inference.build_dataloader(cfg)` reuses `data.loading.instantiate_dataloader`,
also used by training. It requires an explicit inference loader specification;
it does not borrow training shuffle, augmentation, split, or drop-last choices.
Native PyTorch/TorchVision datasets are directly supported. No custom Dataset
or Annotation class is required. The existing project datasets remain optional
for the legacy paired payload. See [Data](data.md#runtime-packaging-for-training-and-inference).

Custom sources may provide arbitrary human annotations or distillation targets.
Their structure is owned by the dataset/collator and configured accuracy metric;
inference does not require any particular annotation class or format. Soft
teacher targets remain soft, and metadata stays attached to the selected targets.
Device selection and `inference_mode` do not select floating precision. See
[Data types and execution precision](../guide/precision.rst) for native/edge
runtime guidance and current execution limitations.

For labeled batches, `predict_dataset(loader)` yields `(predictions, targets)`.
The default selectors split a paired batch before preprocessing/device movement
and model execution. Ground truth remains the selected original object and is
not transformed by inference processors. Apply geometric transforms jointly to
images and targets in the dataset when their coordinates must stay aligned.

Configure standard `operator.itemgetter` or `operator.attrgetter` Hydra targets
for mappings or custom batch objects. For example, processor batches can select
`pixel_values` and `labels`; the existing DetectionBatch selects `images` plus
`batch_idx`, `class_ids`, and `boxes`. Preserve each target's coordinate and
label conventions when selecting a task metric. The same tuple passed to
`predict_batches` remains positional model inputs; the labeled API explicitly
opts into dataset-pair semantics. No inference code imports the training loop.

## Accuracy benchmarking

Benchmarking means inference accuracy against ground truth on a fixed
held-out Dataset. MLflow's official
[PyTorch loading example](https://mlflow.org/docs/latest/ml/deep-learning/pytorch/index.html)
loads the native model and calls it directly. Preserve that contract here.
Its [evaluation examples](https://github.com/mlflow/mlflow/tree/master/examples/evaluation)
demonstrate built-in classifier/regressor metrics, custom metrics/artifacts,
and candidate/baseline comparison through `validate_evaluation_results`.
The [precomputed-prediction example](https://mlflow.org/docs/latest/ml/evaluation/)
allows quality scoring without loading a model or repeating inference.

Those built-in evaluators do not supply detection mAP, segmentation IoU, or
pose metrics. Use established task metric implementations on native predictions
and record results with MLflow; do not flatten structured outputs into
classification labels to satisfy an evaluator. For example,
[TorchMetrics MeanAveragePrecision](https://lightning.ai/docs/torchmetrics/stable/detection/mean_average_precision)
uses COCO evaluation for boxes or instance masks, accepting per-image native
dictionaries. This is a library option, not a newly installed project dependency.
Use a metric's Dataset-level accumulation rather than averaging batch scores.

Comparisons must hold the evaluation samples, annotation interpretation,
metric settings, and comparison policy constant. Record each model's required
normalization, resizing, and native decoding; these may differ by provider. Record immutable model identity,
Dataset Artifact/version, and resolved Hydra settings with each run. MLflow's
[validation example](https://github.com/mlflow/mlflow/blob/master/examples/evaluation/evaluate_with_model_validation.py)
uses `MetricThreshold` and candidate/baseline `EvaluationResult` objects;
thresholds belong to configuration. Keep MLflow metric publication asynchronous
and wait before closing a caller-owned run. Prediction itself does not assume
that ground truth is present or start a benchmark run.

## Verification

Use API-checked mocks for model retrieval and forward-contract tests. Real
local image/mask datasets exercise shared training/inference loading, streaming,
ragged targets, existing detection batches, native ImageFolder classification
with MLflow accuracy persistence, and native COCO boxes/masks via TorchVision.
A local
MLflow integration test also covers training publication, registered-model
alias resolution, and native structured-output predictions for both eager
`pickle` and exported `pt2` serialization. No provider model or dataset download
is required. See the [user guide](../guide/inference.rst) and
[testing instructions](testing.md).
