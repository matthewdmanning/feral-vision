# First training run handoff — 2026-08-01

## Current state

This handoff records the agreement from the 2026-08-01 grilling session and its
in-progress local implementation. Nothing in this document represents a
completed training run or published Dataset Artifact.

## Agreed implementation direction

- Load `yolo11n.pt` through the Ultralytics source adapter and use it as a
  canonical PyTorch `nn.Module`.
- Start with two-class COCO-animal bounding-box detection.
- Materialize immutable lineage from a raw COCO Dataset Artifact to an
  annotation-aware augmented Dataset Variant Artifact.
- The raw artifact must contain its payload, `dataset-artifact.json`, and a
  version-aware tracker.
- Add the detection Task Adapter at
  `src/feral_vision/training/task_adapters/detection.py`. The trainer delegates
  batch handling and loss computation to it; model loading remains in the
  source adapter and augmentation remains in the data layer.
- Preserve native target assignment and calculate classification loss plus
  `torchvision.ops.generalized_box_iou_loss`.
- Co-transform bounding boxes and their class IDs during augmentation. Emit
  augmented rows only—never original and derived duplicates—and preserve source
  cardinality. Keep augmentation seed and probability in the Run Recipe YAML.
- Train exclusively from the augmented Dataset Variant Artifact.

## Implemented locally, pending validation

- `conf/runs/detection.yaml` selects the two-class COCO-animal Dataset Variant,
  `yolo11n.pt`, detection trainer settings, and a seeded annotation-aware
  augmentation concern.
- `materialize_detection_variant` produces one derived image and co-transformed
  YOLO annotation per source image; Dataset Variant publication stores the raw
  Artifact URI and augmentation recipe in its manifest.
- `DetectionTaskAdapter` collates variable-box batches and obtains native
  Ultralytics target assignment before adding generalized IoU to classification
  loss.

The remaining validation must exercise the real installed Ultralytics detector
and compose the detection Run Recipe. Do not claim the acceptance evidence
until those checks and a recorded MLflow run have completed.

## Acceptance evidence

Success requires all of the following:

- verified raw-to-augmented artifact lineage;
- successful model loading without Task Adapter target or loss errors;
- a completed MLflow-recorded run containing the Run Recipe, augmented-artifact
  link, and loss metrics; and
- a selected best Model Artifact.

## Immediate operational prerequisite

The POC Cloud Build handoff is at
`/tmp/feral-vision-poc-cloud-build-handoff-20260801.md`, which supersedes the
older cloud handoff for that work. Before Terraform or dataset preparation,
create the missing `feral-docker` Artifact Registry repository in `us-east4`,
rerun the POC build, verify terminal success, and record the immutable image
digest.

## Scope boundary

This is a training-first handoff. Do not treat the Cloud Build prerequisite as
implementation of the detection training path.
