# Training architecture

Read this before reviewing training code, proposing training refactors, or
classifying training responsibilities for release. The authoritative module
split is [modules.md](../domain/modules.md).

## The training loop belongs in the library

A vision-learning library must implement training. Epoch and batch iteration,
forward passes, loss calculation, backward passes, optimizer and scheduler
steps, validation, checkpoint selection, and experiment tracking are legitimate
library behavior. They do not become production implementation code because
they form an explicit workflow, have an execution order, or call collaborators.

Reusable construction and orchestration can also belong in the library. A
function called `main`, a builder, or a training entrypoint must be assessed by
the choices it fixes, not classified from its name or the presence of control
flow. A function can contain both reusable behavior and a rigid selection;
identify the particular selection rather than excluding the whole function or
file from the release.

## Concrete training choices belong to the implementation

Hydra configuration specifies the concrete training implementation: the
selected Dataset, model, task, augmentation composition, optimization settings,
and other supported training choices. Terraform specifies the concrete cloud
resources and deployment settings. Source code executes those choices; it
does not need to be reduced to passive declarations to qualify as a library.

Common CV tasks must be selectable through structured Hydra configuration
using built-in training implementations. Requiring users to modify Python or
author a loss callback is not sufficient task support. Preserve the low-level
callable seam for library use without making it a prerequisite for common tasks.

Production scripts and Docker entrypoints invoke the configured workflow.
During a library architecture review, use them to discover which source
functions are called, what is supplied, and what is expected back. Their
presence does not make the called training loop production-specific. Changes
to implementation scripts, Hydra recipes, Terraform, or deployment files are
out of scope unless separately requested.

For cloud training, start at Docker loading and execution on the VM, follow
the container entrypoint, and trace calls into the source library. Describe
observed behavior separately from intended contracts. Implementation wiring
problems are context, not automatic library refactor requirements.

## Explicit supported possibilities are valid library code

The library can explicitly enumerate supported computer-vision tasks,
annotation formats, model sources, and the implementations that handle them.
These are finite, meaningful capabilities. A dispatch branch for a supported
format or task is not itself a hardcoded production choice. Supporting one
format does not require converting every other format into it.

Distinguish implementing a supported possibility from fixing the selection:

| Library responsibility | Concrete selection or rigid assumption to identify |
| --- | --- |
| Implement supported annotation readers and their format contracts. | Assume every caller supplies one annotation format regardless of its configured selection. |
| Dispatch a configured task or format to its supported implementation. | Always choose the Feral Vision detection recipe or a particular model/data source. |
| Implement a training loop that uses supplied dependencies and settings. | Embed a particular experiment's paths, classes, augmentation composition, or cloud resources. |
| Implement model-specific behavior in an explicitly selected adapter. | Require that behavior of every model accepted by the generic training contract. |
| Integrate Hydra construction and MLflow tracking with reusable training. | Treat one production configuration or tracking location as the only supported one. |

Keep supported options and their contracts visible. Do not replace a small,
explicit enumeration with a plugin framework, universal annotation hierarchy,
or additional indirection merely to appear generic. Do not promise support for
tasks or formats whose implementation has not been established.

## Reuse without erasing the project's integrations

PyTorch and TorchVision are the primary implementation references. Inspect
their actual dataset, transform, batching, model, and training contracts before
proposing duplicate machinery. Let those libraries perform their own
validation and raise their documented errors; do not add a parallel validation
stack without a demonstrated project requirement.

Existing custom code may provide flexibility needed by Hydra, DVC, or MLflow.
A difference from a tutorial is not sufficient evidence that it should be
replaced. Before recommending replacement, trace callers and configuration and
show that the alternative preserves the required behavior and integrations.
Listing a dependency or saying that TorchVision supplies contracts is not
enough: name the relevant operation, input/output contract, and remaining gap.

Hydra owns training choices; DVC owns Dataset versioning; MLflow owns Run
Records and model tracking. Preserve their established roles. In the current
cloud path, DVC publication is upstream and GPU training consumes the published
Dataset Artifact; see [Program flow](program-flow.md) and
[Cloud Operations](cloudops.md). Do not redesign that workflow during a
library tidy-up.

## Current source: supported choices versus fixed selections

The following describes the current source, not a declaration that its choices
are the desired release contract. Use the concrete distinction when reviewing
it; do not classify the entire training workflow as implementation code.

| Source operation | Observed behavior | Contract distinction |
| --- | --- | --- |
| `training.trainer.build_trainer(cfg)` | Reads model/training choices and injects collaborators; constructs an external `loss_fn` only for the external-criterion path. | Reusable Hydra-based construction. The supplied configuration selects the concrete collaborators. |
| `training.trainer.build_task_adapter(cfg)` | Supplies the compatibility facade only for the selected `detection_giou` execution. | Other supported tasks use the built-in callable selected by Hydra task/provider/loss settings. |
| `models.register_model.model_builder(cfg)` | Reads `cfg.architecture.source`; constructs the configured local class or calls the selected source adapter. | The configured source selects an implementation; a supported source adapter can legitimately contain source-specific code. |
| `training.optim` builders | Use `hydra.utils.instantiate`; bind model parameters to the optimizer and the optimizer to the scheduler. | These short functions preserve the Hydra construction contract. Their size alone does not justify removing them. |
| `config.store.register_configs()` | Registers named data, model, training, optimizer, scheduler, loss, inference, tracking, and augmentation schemas. | Declares supported configuration contracts; registration does not select a particular experiment. |
| `training.trainer.main()` | Retains the existing default recipe path, then calls `build_trainer` and `build_dataloader`. | Recipe selection remains a concrete default; dataset/loader construction is Hydra-selectable, with the legacy AnnotationDataset fallback preserved. |
| `io_utils._load_annotation(path)` | Selects a mask reader from an image suffix and a YOLO box reader from `.txt`; has no separate task/format selection argument. | Current reader selection assumes that suffix identifies annotation meaning. Supporting several standard formats must not be confused with choosing one for every caller. |

The current recipe and Terraform files are evidence of concrete selections,
not library modification targets. In particular, the observed recipe chooses
detection and two classes; that does not mean the generic training code should
fix either value for other callers.

## Hydra selects common task execution

Common tasks require configuration, not a user-authored training callback.
`train.task` accepts `classification`, `detection`, `semantic_segmentation`,
`instance_segmentation`, `panoptic_segmentation`, and `pose`; `generic` retains
an ordinary external criterion. Existing `seg_semantic` and `seg_instance`
configuration names are aliases for the corresponding segmentation tasks.
The selected model must implement that task's documented provider contract.

| Provider/task | `train.loss_mode=auto` | Prepared batch contract |
| --- | --- | --- |
| Tensor-output classification; TorchVision semantic segmentation | External `prediction_loss`; supports tensor logits, `logits` mappings, and TorchVision `out`/`aux` mappings. | Batched image tensors and class indices or class masks. `train.loss_fn` supplies the criterion; `train.aux_weight` selects auxiliary weight. |
| TorchVision detection, instance segmentation, keypoint/pose, or another native-loss model | `model_loss`. | Image lists and per-image native target dictionaries, with masks/keypoints when required. |
| Hugging Face task-head models | `huggingface_loss`. | Processor-prepared keyword inputs and native labels. Returns `output.loss` unchanged, with any `loss_dict` for reporting. It does not recompute provider weighting. |
| Ultralytics detection | Existing `detection_giou`. | Existing BBoxAnnotation samples/collation, preserving the classification plus GIoU objective. |
| Ultralytics classification, instance segmentation, pose | `ultralytics_loss`. | Native batches (`img`, `cls`, boxes, masks, keypoints as appropriate), or tensor image/label pairs for classification. Executes `model.loss`, including mask/keypoint supervision. |

`train.loss_mode` can explicitly select `prediction`, `model`, `huggingface`,
`ultralytics`, or `detection_giou`. For example, `ultralytics` selects the
provider's complete native detection objective instead of the existing custom
GIoU objective. All execution paths use the same optimizer loop. Native
Ultralytics components are logged as `native_loss_0`, `native_loss_1`, etc., in
provider order; their native weighted total is summed once.

`build_trainer` passes the Hydra task selection into model construction.
HF loading selects the matching `AutoModelFor...` class, including universal
segmentation and pose classes, and declares Transformers as a runtime
dependency. `model.architecture.kwargs` forwards native constructor/loading
options through Hydra; `num_classes`, when supplied, maps to HF `num_labels`.
An explicitly selected serialized `.pt`/`.pth` module still loads natively.

Ultralytics head adjustment uses its own `ClassificationModel.reshape_outputs`
for classifiers and its `YOLO.task_map` model class for other tasks. Changing
class count therefore preserves detection, segmentation, or pose model type
and its native criterion. A provider does not gain a task it does not implement
merely because the generic training loop supports that task.

`train.dataloader` is a Hydra `_target_` specification for the prepared dataset
and DataLoader. It can instantiate existing library datasets and transforms;
users do not have to edit the training source. Use `_convert_: all` when a
constructor needs ordinary Python lists/dicts. `train.collate_fn` optionally
selects a collator through Hydra (`_partial_: true` for a function awaiting
samples); a collator explicitly supplied inside the DataLoader specification
takes precedence. Otherwise native vision targets
remain per-image lists, HF ragged instance/mask labels remain lists, and native
Ultralytics tasks use `YOLODataset.collate_fn`. Fixed tensor targets use PyTorch
collation. Processor padding and target preparation remain upstream.

Prepared loader construction is shared with inference through
`data.loading.instantiate_dataloader`. The existing native-vision and HF
collators live in `data.batching`; `training.batching` re-exports them for
compatibility. Native PyTorch/TorchVision datasets do not require project
Annotation classes. For COCO boxes/masks, `CocoDetection` and
`wrap_dataset_for_transforms_v2` provide native target dictionaries, used with
joint v2 transforms and the existing native-vision collator. See
[Data](data.md#runtime-packaging-for-training-and-inference).

Custom data sources may supply human annotations, teacher distributions, or
other structured targets. Supported task/provider examples do not restrict
their representation. `prediction_loss` moves nested target tensors with the
shared `to_device` helper and passes the structure to the configured criterion;
it does not assume integer class IDs or harden distillation labels. The
criterion or native model must accept the chosen target semantics. The existing
loss-callable seam remains available for objectives with other forward/loss
contracts; no universal annotation converter is introduced.
For hardware precision choices and the current absence of shared AMP support,
see [Data types and execution precision](../guide/precision.rst).

Without a configured DataLoader, the existing AnnotationDataset/DatasetSource
fallback remains. Its suffix-based annotation readers are unchanged; selecting
a new task does not silently reinterpret its annotation files. Configure a
compatible prepared dataset/loader for that task rather than changing library
code or redesigning upstream Hydra/DVC acquisition.

Provider-boundary tests use `unittest.mock.create_autospec` and public provider
metadata/output objects, without downloading models or data. Configured task
execution and collation are tested independently of external model correctness.

## Training execution contracts

`Trainer` runs one optimizer loop through the supplied callable:

```python
compute_loss(model, batch) -> tuple[Tensor, dict[str, Tensor]]
```

The first result is the scalar differentiable total, with its selected
weighting and normalization already applied. The dictionary contains named
scalar terms for reporting. Trainer does not sum those terms again. The
callable owns model invocation and task-specific batch preparation; Trainer
owns zeroing gradients, backward, optimizer updates, epoch iteration, scheduler
steps, and checkpoint selection.

### Training folder

| Module | Responsibility |
| --- | --- |
| `trainer.py` | Shared epoch/update loop, monitoring, checkpoint selection, and existing entrypoint/construction compatibility. |
| `execution.py` | External-criterion, TorchVision native, Hugging Face native, and Ultralytics native loss callables. |
| `batching.py` | Compatibility re-exports; shared native-vision and HF collation is implemented in `data/batching.py`. |
| `detection.py` | Independent `collate_detection` and `detection_loss` functions; preserves existing native assignment and classification plus GIoU scaling. |
| `losses.py` | Existing Dice, cross-entropy combination, and supplied-teacher-logit distillation computation. |
| `optim.py` | Existing Hydra construction helpers; training still receives ordinary PyTorch optimizer/scheduler objects. |
| `tracking.py` | Run setup, metadata/lineage, async epoch metrics, and selected-model publication. |
| `task_adapters/` | Small compatibility exports for existing callers; contains no independent detection loss or batching implementation. |

New callers supply `compute_loss` and choose their DataLoader collator
independently. Existing `loss_fn` and `task_adapter` constructor calls remain
supported: they are bound once to the callable at construction, rather than
branching inside every batch. A detector no longer constructs an unused
external criterion merely because `cfg.train.loss_fn` exists. The existing
entrypoint and named configuration inputs remain supported through Hydra.

An explicit `input_example` or `input_example_fn(batch)` may supply an optional
MLflow-supported example independently of loss computation. Examples are not
implicitly extracted from training batches. Native publication does not need
an example and imposes no universal `images` field on a batch.

### Loss and optimizer execution

`prediction_loss` moves tensor inputs/targets to the model device, invokes the
model and calls the supplied external criterion on tensor, `logits`, or `out`
outputs. Optional semantic auxiliary logits use `train.aux_weight`. A composite
criterion uses this same contract. `model_loss` invokes a native vision model
with its image list and target dictionaries, returns the sum of native terms,
and retains their names for reporting. HF and Ultralytics execution preserve
the provider's native loss computation and normalization.

`detection_loss` retains the project's existing model-native assignment and
classification plus GIoU objective. It owns image scaling/device transfer, not
backward or optimization. Its collation function still consumes the existing
BBoxAnnotation representation and stacks equally shaped images. This change
does not migrate annotation formats or replace the selected detector.

The Trainer detaches and accumulates total/component losses on device during
an epoch, then converts epoch averages for logging. The current ordinary
optimizers use one backward and one step per batch. No closure-based optimizer,
AMP path, additional optimizer, or separate training loop is introduced.

### Schedulers and monitored metrics

Ordinary epoch schedulers step after the epoch's updates. ReduceLROnPlateau
steps after validation with `scheduler_monitor`, defaulting to the checkpoint
monitor. Hydra's `train.monitor` names the checkpoint measurement,
`train.mode` selects `min` or `max`, and `train.scheduler_monitor` independently
selects the scheduler metric. These settings avoid dictionary-order dependence.
For existing callers that omit `monitor`, first-validation-metric selection
is retained; when validation has no measurements, selection uses `train_loss`.
The returned `best_loss` key is retained for caller compatibility and contains
the selected metric's best value, including when mode is `max`.

### MLflow logging and completion

`build_trainer` moves the model to `train.device` before optimizer/scheduler
construction, so optimizers bind the final parameter objects. Module criteria
move to that device with their buffers. Direct dependency-injected callers
must bind an optimizer after placing their model and supply a compatible loss.

The Trainer submits one metric dictionary per epoch with native
`mlflow.log_metrics(..., synchronous=False)`. It includes detached loss
components as well as total training loss and validation measurements. No
project logging queue or background thread is added.

Returned `RunOperations` handles are awaited before model publication and
owned-run exit, including cleanup when training fails. Run setup/reuse,
resolved configuration, Dataset lineage, and best-model publication remain
separate from the loss callable and optimizer steps. Model publication
restores the caller's model weights and training mode through `finally`.
Restoration includes individual submodule modes, preserving frozen BatchNorm
or other layers intentionally in evaluation mode. Reusing an existing run
preserves its tracking URI and experiment; recipe tracking settings only
configure a newly owned run.

### Native model publication

Hydra `tracking.serialization_format` defaults to MLflow's `pickle` format.
Publication loads selected checkpoint weights, delegates to
`mlflow.pytorch.log_model`, and lets MLflow perform optional model registration.
It does not run a project inference pass, convert predictions to NumPy, or
require tensor outputs. A missing example does not skip publication.
`tracking.model_name` controls the logged name. Optional `tracking.input_example`
and `tracking.signature` are instantiated by Hydra and passed directly to
MLflow. Supplying an example may trigger MLflow's own forward/signature
inference and serving checks. The `pt2` format remains selectable for models/examples satisfying
MLflow's tracing contract; it is not imposed on every CV model.

Reload structured-output models using `mlflow.pytorch.load_model`; the native
PyTorch model retains its dictionaries, lists, tuples, or provider output
objects. MLflow's standard PyTorch *pyfunc* wrapper has its own tensor-serving
contract; native publication does not promise arbitrary pyfunc serving.

Metadata/artifact/model operations retain their existing MLflow calls; async
metric support does not imply that `log_dict`, `log_artifact` or
`pytorch.log_model` is asynchronous. The code does not reintroduce blanket
exception catches around these operations.
