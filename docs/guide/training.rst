Training
========

Select a Hydra configuration that follows the library contracts in
``src/sightkit_learn/config/``. The files in ``feral-vision/conf/`` are a
collection of configurations previously tried; no single recipe is required
by the generic training runner.

Run in a temporary VM
---------------------

Start inside a prepared Compute Engine container with ``sightkit_learn`` and
the runner files installed. Assume the selected data, model, DVC files and
configs already exist in Cloud Storage. Download them using Google SDKs or
``gcloud`` before invoking the runner. DVC files remain unchanged inputs; the
runner does not perform DVC operations or download inputs itself.

Export these environment variables:

.. list-table:: Runner inputs
   :header-rows: 1
   :widths: 30 70

   * - Variable
     - Value
   * - ``CONFIG_DIR``
     - Absolute local directory containing the selected Hydra configs.
   * - ``CONFIG_NAME``
     - Selected config name, without ``.yaml``.
   * - ``RUN_OUTPUT_DIR``
     - Local output workspace for this attempt; keep inputs separate.
   * - ``TRAINING_DATA_BUCKET_URI``
     - Existing bucket or bucket prefix that will receive run outputs.

From the repository root, run:

.. code-block:: bash

   bash feral-vision/scripts/runs/cloud_train.sh

The runner uses the selected Hydra configuration as written, with no overrides.
Relative paths resolve from ``RUN_OUTPUT_DIR``. Configured absolute checkpoint
and local tracking paths are also collected, under
``external/<absolute-path-without-leading-slash>/``. Their original locations
are recorded in ``output-sources.json``.

Find your outputs
~~~~~~~~~~~~~~~~~

The runner prints the destination and saves it in ``console.log``:

``<TRAINING_DATA_BUCKET_URI>/instances/<numeric-instance-id>/<attempt-id>/``

Each attempt has a new folder. It contains:

* ``console.log``: combined stdout/stderr, including library logs and tracebacks.
* ``resolved-config.yaml`` and, after successful training, ``history.json``.
* The checkpoint at its configured relative path, or under ``external/``.
* Local MLflow files, with SQLite databases exported through consistent backups.
* ``mlflow-export/``: run metadata, metric histories, run artifacts, native model
  packages and registered model version metadata when available.
* Other regular files created in the output workspace.
* ``output-status.json``: the terminal training status, published after the
  other final uploads verify.

The VM identity needs permission to write outputs and read object metadata for
verification. Checkpoint files are replaced atomically: a failed save preserves
the previous best weights. These checkpoints do not contain full
optimizer/scheduler state for resuming training.

Handle completion and failure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The runner pauses 30 seconds between periodic exports and makes a final export
when training ends. It drains the captured logs, verifies cloud sizes and
checksums, then publishes terminal status. Local originals are retained.

A zero runner exit code and ``training_exit_code: 0`` in the terminal record
mean training and export succeeded. A failed training run still exports its
available outputs and logs and retains a nonzero status. Inspect those archived
diagnostics before cleanup or another attempt.

If export fails, keep the VM and local files. Inspect ``console.log`` and local
``export-errors.log`` and recover the export before cleanup. Starting the runner
again starts another training attempt; it is not an export-only retry.

SIGTERM and SIGINT stop the training process group before final export. Allow
enough shutdown grace for that export. Forced VM destruction is an accepted
data-loss case: only completed cloud uploads are assumed to survive.

The runner never deletes the VM. Its caller owns cleanup and must wait for
verified output preservation, including for a failed training run.

Availability
~~~~~~~~~~~~

The scripts are mirrored in ``src/templates/scripts/runs/`` and included by
the training Dockerfile when an image is built. The existing detection
Terraform deployment does not select this runner automatically. No new VM/GPU
deployment or image rebuild has been validated as part of this change.

Training and tracking errors
----------------------------

The trainer no longer suppresses errors in configuration resolution, Dataset
lineage verification, MLflow setup/logging, or best-model publication. A
configured training run can therefore fail at these operations rather than
finish without recording the failure. No tracking configuration still means
the trainer runs without opening an MLflow run.

Best-model publication restores the current model weights and every submodule's
training mode, including frozen evaluation layers, even if publication fails. Model-source discovery reports an adapter import
or construction failure directly rather than hiding it as a missing adapter.

Training execution
------------------

The training loop accepts ``compute_loss(model, batch)``, returning a
scalar differentiable total and a dictionary of named scalar loss tensors.
The loop handles backward and optimizer updates once for both ordinary and
model-specific losses. ``training.execution.prediction_loss`` supports an
external criterion; ``model_loss`` supports TorchVision detectors returning
native loss dictionaries. Detection collation and the existing native-assigned
classification/GIoU loss live independently in ``training.detection``.

Existing ``loss_fn`` and ``task_adapter`` callers remain supported. The latter
is a compatibility facade, not a second optimizer path. Model publication
inputs can be supplied through ``input_example`` or ``input_example_fn``.

Epoch total/component losses and validation metrics are submitted together
using MLflow's native asynchronous logging. Training waits for submitted
operations before publishing the selected model and ending its owned run.
Metadata and model/artifact publication keep their existing MLflow operations.

An active caller-owned MLflow run keeps its tracking store and experiment.
Recipe tracking settings apply when training opens its own run. The trainer
does not close a caller-owned run.

``build_trainer`` places the model on ``train.device`` before constructing its
optimizer and scheduler. Module criteria move to that device too, including
buffers such as class weights. Direct ``Trainer`` callers should place the
model before binding its optimizer and supply a device-compatible criterion.

``monitor`` explicitly selects a checkpoint metric; ``mode`` is ``min`` or
``max``. ``scheduler_monitor`` independently selects the measurement supplied
to ``ReduceLROnPlateau`` after validation. Other existing epoch schedulers use
ordinary ``step()``. For compatibility, callers omitting ``monitor`` retain
selection by the first validation metric, or training loss when there are no
validation measurements.

Hydra task and provider selection
---------------------------------

Select ``train.task`` from ``classification``, ``detection``,
``semantic_segmentation``, ``instance_segmentation``, ``panoptic_segmentation``,
or ``pose``. The selected model must implement the chosen task. With
``train.loss_mode=auto``, the library selects tensor/semantic-logit criteria,
TorchVision native losses, Hugging Face task-head native losses, or Ultralytics
native losses. Ultralytics detection retains the existing classification/GIoU
objective; choose ``train.loss_mode=ultralytics`` for its full native objective.
Mask and keypoint tasks execute their native supervised losses.

No user-authored loss callback is required for these paths. Hugging Face uses
task-head ``AutoModelFor...`` classes. ``model.architecture.kwargs`` supplies
native loading/constructor options; class-count changes preserve Ultralytics'
model task through its own task map/head-adjustment functions.

``train.dataloader`` is a Hydra specification for the already-prepared dataset
and loader. It can instantiate existing library datasets and transforms. Its
explicit collator takes precedence, followed by ``train.collate_fn`` and the
built-in provider/task collator. Use ``_convert_: all`` for constructors needing
ordinary Python lists or dictionaries. Variable instance labels, masks, and
keypoints retain their native structures. Data processing/padding remains
upstream; the legacy DatasetSource annotation reader is not reinterpreted when
a different task is selected.

Hydra loader construction is shared with inference in
``data.loading.instantiate_dataloader``. The native-vision and Hugging Face
collators live in ``data.batching``; their old ``training.batching`` imports
continue to work. Standard datasets can be used directly; custom Dataset or
Annotation objects are optional. For COCO boxes/masks, TorchVision's
``CocoDetection`` plus ``wrap_dataset_for_transforms_v2`` produces native target
dictionaries and jointly transformed images. See :doc:`dataset`.

Custom data sources can supply distillation distributions or structured human
annotations as targets. The external-criterion path moves nested target tensors
to the model device and preserves their structure and non-tensor metadata for
the configured loss. The loss determines their interpretation; it must accept
the selected target contract. Soft-target distillation can use native PyTorch
criteria such as ``KLDivLoss`` with student log-probabilities and teacher
probabilities.
See :doc:`precision` for FP16/BF16 training practices, hardware choices, and
the current absence of shared AMP configuration.

For example, a component configuration for a prepared tensor classifier can
select existing PyTorch assets entirely through Hydra::

   train:
     task: classification
     loss_mode: auto
     loss_fn:
       _target_: torch.nn.CrossEntropyLoss
     dataloader:
       _target_: torch.utils.data.DataLoader
       _convert_: all
       dataset:
         _target_: torchvision.datasets.ImageFolder
         root: ${data.root}/images
         transform:
           _target_: torchvision.transforms.Compose
           transforms:
             - _target_: torchvision.transforms.Resize
               size: [256, 256]
             - _target_: torchvision.transforms.ToTensor
       batch_size: ${train.batch_size}

Choose a prepared dataset implementing the selected task's native targets.
The example's class-directory ImageFolder layout is a selectable library input,
not a change to the existing production Dataset layout or Run Recipe.

MLflow publication
------------------

``tracking.serialization_format=pickle`` uses MLflow's native PyTorch model
serialization without a project inference pass or a required example/output
conversion. Dictionaries, lists, tuples, and provider output objects remain
part of the native model's behavior. Publication records the selected weights
and restores the caller's current weights and mode afterward.

``tracking.model_name`` selects the logged model name. Optional
``tracking.input_example`` and ``tracking.signature`` are Hydra-instantiated
MLflow arguments. ``tracking.serialization_format=pt2`` is available when the
selected model and explicit example/signature satisfy MLflow's tracing rules.
Native reloading uses ``mlflow.pytorch.load_model``; MLflow's PyTorch pyfunc
serving wrapper separately supports a tensor interface. Supplying an example
can cause MLflow to execute its own signature inference or serving validation.
Examples and signatures must match that native MLflow contract; they do not
impose tensor-only outputs on native model publication.

Dataset boundary in the detection deployment
--------------------------------------------

Dataset versioning and publication happen upstream of GPU training. The
published Dataset Artifact is the handoff boundary. Training requires its
``payload/images/``, selected annotations, and ``dataset-artifact.json``.

``dataset-artifact.json`` is the provenance record consumed by training. The
GPU workflow does not initialize DVC, generate a new ``dvc.lock``, or reproduce
the dataset. Deployment preflight parses the published manifest and records its
SHA-256; VM startup stages and re-hashes the exact manifest before training.
The container verifies the same SHA-256 again before starting the trainer.

Detection training image
------------------------

The only supported GPU training image is ``feral-vision/deploy/Dockerfile.gcp``. Build it
through ``feral-vision/scripts/cloud/build_training_image.sh``, which uses
``feral-vision/deploy/cloudbuild.training-image.yaml`` and returns a digest-pinned Artifact
Registry reference for Terraform.

The image build composes ``runs/detection`` and imports the core runtime before
it can be pushed. GPU availability is verified later on the actual training VM.
Check Artifact Registry for an existing image before requesting a build.
Verify the selected digest against the run requirements; image age and commit
timestamps do not determine whether a build is needed.

Existing detection deployment
-----------------------------

Preflight needs no local Docker. It confirms the deployment image digest
exists in Artifact Registry. It also parses the rendered startup script and
checks SSD path containment and container mappings. It never downloads images
or weights.

Use Terraform 1.16 or later within 1.x and the locked Google provider 8.x.
The validated toolchain is Terraform 1.16.6 with Google provider 8.7.0.

Run ``feral-vision/terraform/preflight/preflight.py`` with the exact intended Terraform
inputs before every apply. A passing preflight produces a saved Terraform plan
and ``deployment-manifest.json`` containing the plan SHA-256, digest-pinned
training image, Dataset Artifact URI, and Dataset Artifact manifest SHA-256.

Apply only through::

   feral-vision/scripts/runs/detection.sh --manifest feral-vision/terraform/preflight/reports/<timestamp>/deployment-manifest.json

The launcher rejects a changed plan, collects startup logs, waits for terminal
``training-evidence.json``, and verifies that the Dataset Artifact manifest hash
observed by the VM matches the hash approved during preflight.

A VM reaching ``RUNNING`` is not training success. Terminal training evidence
is the authoritative run result.

Run metadata
------------

MLflow records the resolved training configuration and the exact
``dataset-artifact.json`` used by the run, including its SHA-256. The startup
workflow also preserves that manifest beside terminal run evidence in the
operational artifact prefix.
