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

For this baseline, COCO annotations are converted upstream in the Variant
materialization build to YOLO detection boxes. The binary class contract is
stable: `cat` is class `0`; every other selected COCO animal is class `1`
(`not-cat`). Invalid or fully out-of-frame COCO boxes are excluded. The raw
Dataset Artifact remains unchanged.

## Cloud run configuration

The isolated cloud configuration is under `terraform/runs/detection_first_run_augmented/`. It
creates only the run-specific VM and consumes existing networking, image-pull,
and dataset-read access. It imports the existing training subnet and provisions
Cloud NAT scoped to that subnet for private VM egress. Its separate state prefix
isolates this run's resources.

Before planning, supply a digest-pinned image built with
`deploy/runs/detection_first_run_augmented/cloudbuild.training-image.yaml`, the immutable Dataset
Variant Artifact prefix, the existing VM service-account email, and a writable
non-dataset GCS MLflow artifact prefix. The run startup creates a local MLflow server on the
VM loopback interface, stages the payload, manifest, and tracker to SSD, then
starts `runs/detection_first_run_augmented`; it never runs augmentation or DVC.

The MLflow tracking URI is not an input: startup creates
`http://127.0.0.1:5000` on the disposable VM and the training container reaches
it through host networking. The artifact prefix is dedicated non-dataset GCS
storage. See [ADR 0002](../adr/0002-first-augmented-detection-cloud-run.md) for
the complete topology and ownership boundaries.

`scripts/cloud/prepare_detection_first_run_augmented.sh` creates an immutable
run manifest and a fresh plan, but never applies it. After review,
`scripts/runs/detection_first_run_augmented.sh` applies precisely that plan and
collects the startup, preflight, and MLflow Run Record evidence.

## Validation status

Local unit, configuration-composition, type, and lint checks cover this
implementation. A completed MLflow-recorded fine-tuning run and publication of
the required Dataset Artifacts remain operational acceptance work.
