# First augmented detection baseline

## Recipe

`conf/runs/detection_first_run_augmented.yaml` is the first two-class COCO-animal fine-tuning
baseline. It selects the immutable annotation-aware Dataset Variant Artifact,
the default 80-class `yolo11n.pt` detector, two-class training settings, and the seeded
`coco_animals_detection_first_run_augmented` augmentation concern.

This run selects `yolo11n_default`, whose configured class count matches the
pretrained detector's default head and therefore transfers it unchanged. The
source adapter retains the optional configured-head rebuild capability for a
later run that explicitly selects a different class count.

## Data contract

Prepare the raw COCO Dataset Artifact upstream, then materialize and publish a
new immutable Dataset Variant Artifact. Its payload must contain the canonical
`images/` and `annotations/` layout, one co-transformed YOLO annotation per
derived image, `dataset-artifact.json`, and a version-aware DVC tracker.

The Variant Artifact manifest records the raw Artifact URI plus the exact
augmentation seed and operations. Training must use the Variant Artifact only;
it must never fall back to the raw Artifact.

## Cloud run configuration

The isolated cloud configuration is under `terraform/runs/detection_first_run_augmented/`. It
creates only the run-specific VM and consumes existing networking, image-pull,
and dataset-read access. Its separate state prefix prevents overlap with the
shared cloud-smoke configuration.

Before planning, supply a digest-pinned image built with
`deploy/runs/detection_first_run_augmented/cloudbuild.training-image.yaml`, the immutable Dataset
Variant Artifact prefix, the existing VM service-account email, and an HTTPS
MLflow tracking endpoint. The run startup stages the payload, manifest, and
tracker to SSD, then starts `runs/detection_first_run_augmented`; it never runs augmentation or DVC.

## Validation status

Local unit, configuration-composition, type, and lint checks cover this
implementation. A completed MLflow-recorded fine-tuning run and publication of
the required Dataset Artifacts remain operational acceptance work.
