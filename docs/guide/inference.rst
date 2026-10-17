Inference
=========

Inference loads a model already published to MLflow and returns its native
predictions. Classification, segmentation, detection, and pose models retain
their own input/output contracts. Configuration uses Hydra; no new task adapter
or user-written prediction callback is required for native execution.

Configuration
-------------

Select inference settings through the registered ``InferenceConfig`` schema in
your component configuration. For example::

   inference:
     model_uri: models:/vision@champion
     device: cpu
     call_mode: auto
     load_kwargs: {}
     forward_kwargs: {}
     preprocess: null
     postprocess: null

   tracking:
     tracking_uri: sqlite:///tracking.db

``model_uri`` accepts MLflow artifact paths, logged-model URIs, registered model
versions such as ``models:/vision/3``, and aliases such as
``models:/vision@champion``. The tracking URI can also come from the existing
MLflow environment when no tracking configuration is supplied. Inference does
not require an experiment name or start an MLflow run.

The library API consumes the composed configuration::

   from sightkit_learn.inference import build_predictor

   predictor = build_predictor(cfg)
   predictions = predictor.predict(prepared_batch)

``build_predictor`` loads once through ``mlflow.pytorch.load_model``. Reuse the
predictor for subsequent batches; rebuild it to resolve a changed registry
alias. ``load_kwargs`` forwards native loading options. The selected device is
also the default map location for eager model weights.

Inputs and outputs
------------------

In ``auto`` call mode, tensors and image lists are passed as one argument,
mappings are expanded as keyword inputs, and tuples are expanded as positional
arguments. This accommodates tensor classifiers, TorchVision variable-size
image lists, and Transformers processor outputs. Use ``positional``, ``args``,
or ``kwargs`` explicitly when the model requires a different convention.
``forward_kwargs`` supplies native options such as a supported ``return_dict``.

Inputs are already prepared for the selected model. Nested tensors move to the
configured device. Prediction runs under ``torch.inference_mode``; eager model
evaluation setup is delegated to MLflow. Exported models retain their captured
behavior and are not switched to evaluation mode again.
See :doc:`precision` for GPU/edge dtype choices. Device selection and
``inference_mode`` do not enable mixed precision or change model/input dtype.

Outputs remain intact: logits, dictionaries, detection/instance lists, pose
outputs, tuples, and Transformers output objects are returned without forcing
a tensor-only or NumPy interface. Use native ``mlflow.pytorch`` publication and
loading for these models; this path does not use MLflow's tensor-only PyTorch
pyfunc prediction wrapper.

Configured processing
---------------------

Optional ``preprocess`` and ``postprocess`` Hydra targets select existing library
or provider callables. For a tensor classifier, probability conversion can be
selected without changing Python::

   inference:
     postprocess:
       _target_: torch.nn.Softmax
       dim: 1

A function awaiting its runtime input uses ``_partial_: true``. Provider
processors needing additional fixed arguments can use Hydra-configured
``functools.partial``. Choose the processing appropriate to the model's native
contract. No universal image resizing, confidence filtering, mask cleanup, or
test-time augmentation is applied implicitly. Existing task-specific threshold,
augmentation, and mask-area settings affect predictions when explicitly
referenced by those provider options or processors.

For a prepared batch stream::

   for predictions in predictor.predict_batches(prepared_batches):
       consume(predictions)

The stream yields one native result per batch without loading another model or
collecting every prediction in memory. Data retrieval and prepared-batch
construction remain upstream.

Labeled datasets
----------------

Use native PyTorch/TorchVision datasets directly through Hydra. The inference
loader uses the same construction function as training and retains a collator
explicitly selected inside the loader specification. ``inference.collate_fn``
provides an optional fallback; otherwise PyTorch supplies its default collation.
Project-specific Dataset and Annotation objects are optional.

Custom sources may supply human annotations, teacher probabilities, embeddings,
or other structured targets. The dataset/collator and chosen accuracy metric
define their meaning. Labeled inference preserves that structure, including
soft distillation targets and annotation metadata, without imposing a standard
annotation format.

For example, a held-out classification Dataset can use ``ImageFolder``::

   inference:
     model_uri: models:/vision/3
     dataloader:
       _target_: torch.utils.data.DataLoader
       _convert_: all
       batch_size: 16
       shuffle: false
       drop_last: false
       dataset:
         _target_: torchvision.datasets.ImageFolder
         root: ${data.root}/images
         transform:
           _target_: torchvision.transforms.v2.Compose
           transforms:
             - _target_: torchvision.transforms.v2.ToImage
             - _target_: torchvision.transforms.v2.ToDtype
               dtype:
                 _target_: hydra.utils.get_object
                 path: torch.float32
               scale: true

Select the held-out root and the model's required transforms in configuration.
``ImageFolder`` obtains labels from class directories. Preserve the training
class-index interpretation when comparing them with predictions.

The labeled dataset API separates inputs from targets before model execution::

   from sightkit_learn.inference import build_dataloader, build_predictor

   predictor = build_predictor(cfg)
   loader = build_dataloader(cfg)
   for predictions, targets in predictor.predict_dataset(loader):
       consume(predictions, targets)

By default, labeled batches are ``(inputs, targets)`` pairs, including PyTorch's
collated list form. Targets remain the original selected objects; prediction
preprocessing and postprocessing affect only model inputs and predictions.
Use joint dataset transforms for image/target geometry. The loader retains its
configured order, final partial batch, sampling, and worker settings.

Mappings and existing custom batch objects can use standard Hydra callables.
For a prepared Hugging Face mapping with ``pixel_values`` and ``labels``::

   inference:
     input_selector:
       _target_: operator.itemgetter
       _args_: [pixel_values]
     target_selector:
       _target_: operator.itemgetter
       _args_: [labels]

This selects the pixel tensor as the model's first positional input. Select
all additional inputs required by the chosen provider contract. Likewise,
``operator.attrgetter`` can select ``images`` and native target fields from
the existing ``DetectionBatch``. No user-authored selector is required for
these standard cases.

For native COCO detection/instance targets, use ``CocoDetection`` with
``wrap_dataset_for_transforms_v2`` and
``sightkit_learn.data.batching.collate_vision``; see :doc:`dataset`.
``AnnotationDataset`` and ``StreamingAnnotationDataset`` also remain available
for the existing stem-matched payload, with explicit target conversion when
required by a consumer.

Use ``predict_batches`` for input-only streams. It preserves model tuples as
multiple positional inputs; it does not interpret them as labeled pairs.

Accuracy benchmarking
---------------------

Benchmarking evaluates predictions against ground truth on a fixed evaluation
Dataset. MLflow's `evaluation examples <https://github.com/mlflow/mlflow/tree/master/examples/evaluation>`_
show built-in classifier/regressor metrics, custom metrics and artifacts, and
candidate/baseline comparison with ``mlflow.validate_evaluation_results``.

For classification, MLflow can score precomputed class predictions without
running inference again::

   import mlflow
   import pandas as pd

   evaluation_data = pd.DataFrame({
       "prediction": predicted_labels,
       "target": ground_truth_labels,
   })
   with mlflow.start_run(run_name="accuracy-benchmark"):
       result = mlflow.models.evaluate(
           data=evaluation_data,
           predictions="prediction",
           targets="target",
           model_type="classifier",
           evaluator_config={"log_explainer": False},
       )

   accuracy = result.metrics["accuracy_score"]

This classification example assumes class decisions have already been derived
using the selected model's output contract. MLflow also provides precision,
recall, F1 and confusion-matrix artifacts. Probability-dependent metrics need
probability outputs through an evaluator-compatible model interface; class
decisions alone are insufficient for ROC-AUC or log loss.

Detection, segmentation, and pose need task-specific scores. MLflow's built-in
classifier/regressor evaluators do not calculate detection mAP, mask IoU, or
keypoint quality. Retain native predictions and use an established task metric
implementation, then record its scores with ``mlflow.log_metrics`` using
``synchronous=False`` and wait for the returned operation before ending the
run. Do not average per-batch mAP or IoU values: use the metric implementation's
Dataset-level accumulation and reduction.

For candidate/baseline comparisons, use the same held-out samples, annotation
interpretation, metric settings, and comparison policy. Each model may need
its own normalization, resizing, or native decoding; record those required
processing settings rather than imposing another provider's pipeline. Record
the Dataset Artifact/version, immutable model versions or logged model IDs,
and resolved Hydra configuration. MLflow's
`model validation example <https://github.com/mlflow/mlflow/blob/master/examples/evaluation/evaluate_with_model_validation.py>`_
evaluates both models and passes their results to
``mlflow.validate_evaluation_results`` with ``MetricThreshold`` criteria for
absolute scores and improvements over the baseline. These criteria are
configuration choices rather than hard-coded promotion rules.
