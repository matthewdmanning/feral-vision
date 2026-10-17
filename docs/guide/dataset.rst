Datasets, publication, and DVC
==============================

Ownership and actual process
----------------------------

Workflow scripts acquire and transform data. DVC registers each selected,
prepared Dataset with ``dvc add`` and uploads its cached contents with
``dvc push``. A Dataset Variant is registered the same way as a raw Dataset.
There is no fixed raw/preprocessed/augmented DVC pipeline or ownership of those
entire parent directories. The old ``dvc.yaml`` and its acquisition/processing
wrappers have been removed; existing Dataset files are preserved.

The unit of registration is one Dataset root containing ``images/`` and
``annotations/``. Each root has one sibling ``<root>.dvc`` metadata file.
Select separate, non-overlapping roots for the raw Dataset and each Variant.
Their names and locations come from the producing workflow; DVC does not
require specific raw or augmented parent directories. Do not register the
repository's entire ``data/`` tree.

The intended flow is::

   acquire if absent -> raw Dataset -> register with DVC
                           |
                           +-> modify if requested and Variant absent
                                  -> Dataset Variant -> register with DVC

   selected registered Dataset -> retained payload + manifest publication
                               -> GPU staging -> training and MLflow evidence

Reuse a verified existing Dataset or Artifact. Acquisition, registration, and
publication are separate operations; an existing upstream result must not be
recreated merely to start training.

The local registration command is implemented. The cloud acquisition/publication
build still bypasses it; connecting the exact DVC version to the retained
manifest remains open work. See ``ACTION_ITEMS.md``. GPU training continues to
consume an already-published Artifact and does not run DVC.

Register one prepared Dataset
-----------------------------

Requirements:

* Git and DVC are initialized in the current repository. This checkout already
  contains ``.dvc/``. Use the locked DVC 3.67.1 with GCS support; Bash and
  ``realpath`` are required by the shell entrypoint.
* The selected directory exists inside that repository and contains
  ``images/`` and ``annotations/``. The registration script checks these
  directories and repository containment; the producer must validate actual
  data completeness, annotation format, and provenance before registration.
* A default DVC remote is configured with credentials and permission to upload.
  The project's durable remote is the dataset-only bucket's ``/dvc`` prefix.
  No bucket URI is stored as an unexpanded environment variable in tracked
  configuration. Local remote configuration stays in ``.dvc/config.local``.

Export ``TRAINING_DATA_BUCKET_URI`` with the existing dataset-only bucket URI.
Run this from the repository root to configure the remote; it does not create a
bucket or upload data:

.. code-block:: bash

   bash -euc '
   : "${TRAINING_DATA_BUCKET_URI:?Export the dataset-only bucket URI}"
   uv tool run --from "dvc[gs]==3.67.1" dvc remote add --local --default --force gcs "${TRAINING_DATA_BUCKET_URI%/}/dvc"
   '

Then export ``DATASET_ROOT`` as the selected prepared Dataset directory. This
command records and uploads it:

.. code-block:: bash

   bash -euc '
   : "${DATASET_ROOT:?Export the selected prepared Dataset directory}"
   uv tool run --from "dvc[gs]==3.67.1" bash scripts/data/register.sh "$DATASET_ROOT"
   '

``scripts/data/register.sh`` verifies the directory, requires a default remote,
then runs these operations for exactly that root:

.. code-block:: bash

   dvc add "$dataset_root"
   dvc push "${dataset_root}.dvc"

This last snippet describes the script internals; use the complete operator
command above. Registration does not download, preprocess, augment, synchronize
an entire plain-data tree, publish the training manifest, or require ``gcloud``.
A failed upload remains a failed registration; the shell stops and reports
DVC's error. It does not automatically retry or publish a success manifest.

Outputs are the sibling ``.dvc`` metadata, a Git ignore update, local cache
entries, and uploaded DVC cache objects. No ``dvc.lock`` is created or required.
Retain the ``.dvc`` and ignore changes in Git using the normal commit/PR workflow.
The repository's ignore rules allow these files under ``data/`` while keeping
Dataset contents ignored. ``dvc push`` transfers data; it does not publish Git
metadata. See the official `add reference
<https://dvc.org/doc/command-reference/add>`_ and `push reference
<https://dvc.org/doc/command-reference/push>`_.

DVC records content identity, not how those contents were produced. Retain
source Dataset identity, operations, resolved configuration, image order, and
random seed in provenance, linked to the selected ``.dvc`` version. The custom
publisher does not yet establish this link automatically.

Inspect local state without using the Windows project virtual environment:

.. code-block:: bash

   uv tool run --from 'dvc[gs]==3.67.1' dvc status --json

``{}`` means local tracked contents match their recorded state; it does not
prove remote availability or that a Dataset has been registered at all.
A fresh checkout with no registered Dataset can also report ``{}``.

Dataset formats and producer responsibilities
---------------------------------------------

The legacy ``DatasetSource`` reader scans immediate children of ``images/`` and
``annotations/`` and matches filenames by stem. YOLO ``.txt`` rows contain class
index and normalized ``x_center y_center width height``. Masks use ``.png``,
``.jpg``, ``.jpeg``, or ``.bmp``. ``names.yaml`` is excluded from matching.
That reader has no classification JSON or COCO JSON support. Other dataset
readers are selectable through Hydra: native ``torchvision.datasets.ImageFolder``
and ``CocoDetection`` require neither custom Annotation objects nor conversion
to the legacy reader's format. Dataset publication layout and the selected
runtime reader's sample contract are separate concerns.

The implemented producers have different contracts:

* ``fetch_coco`` writes nested ``images/coco_train2017/`` and
  ``annotations/coco_train2017/instances_train2017_animals.json`` under its
  configured root. It reuses existing files and skips failed image downloads
  after logging warnings. Completion alone does not prove a complete Dataset.
* ``export_coco_train2017`` in ``scripts/pull_coco_train2017.py`` uses FiftyOne's
  COCO 2017 train detection zoo and the ten animal classes, with a sample limit
  of ``max_epochs * batch_size``. It writes flat ``images/`` and
  ``annotations/instances.json`` and refuses an existing export directory.
* ``preprocess`` in ``data/transforms.py`` transforms one image in memory; it
  is not a Dataset-producing stage. The older image-only ``run_augment_stage``
  does not preserve detection annotations and is not the registration workflow.
* ``materialize_detection_variant`` co-transforms YOLO boxes and images using
  the configured operations and ``seed + image_index``. Its producer must retain
  the source Artifact link, operations, seed, and ordering as lineage.

COCO acquisition requires either a compatible native reader or conversion for
the legacy per-image annotation reader. Registering raw COCO with DVC is valid;
the Training Script must select a reader and transforms matching its format.

Runtime batches
---------------

Training and inference use PyTorch DataLoaders constructed by Hydra through
the shared ``data.loading.instantiate_dataloader`` function. Native fixed
tensor/label samples use PyTorch's default collation. The existing
``data.batching.collate_vision`` retains variable-size image lists and per-image
target dictionaries; ``collate_huggingface`` retains ragged processor labels.
The former ``training.batching`` import paths remain available.

For native COCO boxes and masks, select ``torchvision.datasets.CocoDetection``
inside ``torchvision.datasets.wrap_dataset_for_transforms_v2`` with
``target_keys: [boxes, labels, masks]``. Configure joint v2 transforms on the
underlying dataset and ``collate_vision`` on its DataLoader. TorchVision supplies
the typed XYXY boxes and masks; no project annotation class is required. See
the `official v2 example <https://docs.pytorch.org/vision/stable/auto_examples/transforms/plot_transforms_e2e.html>`_.

Existing ``AnnotationDataset`` and ``StreamingAnnotationDataset`` remain
supported for stem-matched payloads. They yield CHW image tensors with decoded channel count/bit depth and loaded
Annotation objects; their optional ``target_transform`` can select a tensor
representation. These custom datasets are compatibility options, not a
required representation for training or inference.

Custom sources may yield arbitrary annotation structures from human annotation,
distillation, or other upstream processes. Configure the dataset and collator
to retain the structure expected by the chosen model/loss/metric. Soft teacher
distributions do not become hard labels automatically. The configured external
training criterion can receive nested targets with tensors moved to the model's
device; non-tensor metadata is retained.

Labeled inference keeps targets outside the model call and yields them beside
native predictions for accuracy scoring. See :doc:`inference` for configuration
and :doc:`training` for task-specific training batch contracts.

Cloud publication: existing implementation
------------------------------------------

``deploy/cloudbuild.prepare.yaml`` runs two images sharing ``/workspace``:

1. ``_ACQUISITION_IMAGE`` runs ``scripts/cloud/acquire_data_subset.sh`` with
   ``MAX_EPOCHS`` and ``BATCH_SIZE`` (build defaults 50 and 16). It writes
   ``payload/images/``, ``payload/annotations/instances.json``, and
   ``dataset-input.json``. Metadata contains ``dataset``, ``source``, and
   ``provenance`` with classes, sample limit, and ``random_seed: null``.
2. ``_DVC_IMAGE`` runs ``scripts/cloud/publish_dataset_artifact.sh`` and calls
   ``publish_dataset_artifact``. Despite the image substitution name, it runs
   no DVC commands. Its Dockerfile is now
   ``deploy/dataset-publisher/Dockerfile``, selected by
   ``deploy/cloudbuild.dvc-image.yaml``.

Required substitutions are ``_ACQUISITION_IMAGE``, ``_DVC_IMAGE``,
``_TRAINING_DATA_BUCKET_URI``, ``_DATASET_ARTIFACT_PREFIX``, and
``_GCS_URI_PREFIX``. Supply reviewed digest-pinned images, an existing
dataset-only bucket URI, a new reviewed Artifact prefix, and the URI
scheme/separator from configuration. Image pinning is an operator requirement; the YAML
does not enforce it. Verify the configured build service account before use.

The publisher needs Python, the project publication module,
``google.cloud.storage``, credentials, and object creation/retention permissions.
Its shell requires exported ``TRAINING_DATA_BUCKET_URI``,
``DATASET_ARTIFACT_PREFIX``, and ``GCS_URI_PREFIX``. Optional inputs are
``DATASET_PAYLOAD_DIR`` (default ``/workspace/payload``), ``DATASET_INPUT_PATH``
(default ``/workspace/dataset-input.json``), and ``DATASET_RETENTION_DAYS``
(default 365, at least one). Acquisition carries FiftyOne and MongoDB in its
own image; publication does not need those dependencies.

The publisher checks directories and basic metadata, not annotation semantics,
non-empty payloads, or full provenance. It uploads each file with
``if_generation_match=0`` and Unlocked retention, then writes
``dataset-artifact.json`` last. The manifest carries input metadata plus
``files[relative_path] = {sha256, generation}``. Success prints the Artifact URI::

   <TRAINING_DATA_BUCKET_URI>/<DATASET_ARTIFACT_PREFIX>/
     payload/images/...
     payload/annotations/...
     dataset-artifact.json

A failed publication can leave a partial prefix. Diagnose before retrying and
use a new reviewed prefix for a fresh publication. This custom publication still
needs integration with the exact registered DVC Dataset version.

Remaining training seam
-----------------------

``scripts/cloud/materialize_detection_variant.sh`` ends by importing the absent
``publish_dataset_variant_artifact``. Its per-image YOLO output also conflicts
with preflight/startup's requirement for a pinned
``payload/annotations/instances.json`` generation. Resolve these gaps before
claiming an end-to-end GPU workflow.

GPU preflight currently checks a non-empty JSON manifest, its hash, an images
prefix, and the pinned COCO object; it does not validate every listed file/hash
or prove annotation compatibility. The VM stages the published input on local
SSD, and MLflow and terminal evidence record its manifest SHA-256. See
:doc:`training` for the deployment workflow. No live cloud or GPU validation was
performed for this redesign.
