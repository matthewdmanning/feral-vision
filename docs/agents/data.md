# Data and ingestion

Use this guide when changing data ingestion, dataset layout, or dataset
publication. Data operation entrypoints live in
[`feral-vision/scripts/data/`](../../feral-vision/scripts/data/).

## Data flow

`Data Source Adapter -> request -> optional transform or format -> Dataset`

`Dataset -> modification -> Dataset Variant`

`Dataset or Dataset Variant -> Publish -> Dataset Artifact`

A Dataset Variant is a Dataset. The `dataset-artifact.json` manifest owns the
file list of a Dataset Artifact.

The existing publication workspace has `images/` and `annotations/` directories.
The selected format determines annotation packaging; COCO can use a shared
`annotations/instances.json`. The legacy `DatasetSource` reader instead matches
annotation files to image stems: masks use `.png` or `.jpg`, YOLO boxes use
`.txt`, and `names.yaml` records class indices. That reader does not
support classification JSON or raw COCO JSON and scans only immediate children
of these directories. Its limitations are not requirements on other dataset
readers: Hydra can instantiate native PyTorch/TorchVision datasets directly.
For example, `ImageFolder` reads class directories and `CocoDetection` reads
COCO JSON; neither requires project Annotation objects or a format conversion.
The COCO output from `feral-vision/scripts/fetch.py` is incompatible with the legacy reader;
select a compatible native reader when consuming that format.

## Runtime packaging for training and inference

`data.loading.instantiate_dataloader` shares Hydra construction between the
training and inference builders. A collator inside the DataLoader specification
takes precedence over the builder's collator. `data.batching` contains the
existing native-vision and Hugging Face collators; their former
`training.batching` paths remain compatibility imports. PyTorch default
collation remains suitable for fixed tensors and class/mask targets.

Dataset readers and transforms establish the native sample contract. For COCO
boxes/masks, TorchVision's `wrap_dataset_for_transforms_v2` wraps `CocoDetection`
and supplies per-image `boxes`, `labels`, and `masks`; v2 transforms operate
jointly on the image and typed targets. This reader/wrapper path is tested
without downloading data. Retain native dataset structures whenever they fit.

Custom sources are also valid, including human annotation and distillation.
Their targets can be soft distributions, masks, keypoints, embeddings, polygons,
or other structures accepted by the configured consumer. The examples above
are not an annotation whitelist. Select a Dataset/IterableDataset and collator
that retain the required structure; the loss or accuracy metric determines its
meaning. Shared loader construction and labeled inference do not infer labels,
convert teacher targets to hard classes, or require Annotation subclasses.
Device transfer preserves target dtypes. Read the
[precision guide](../guide/precision.rst) before changing image scaling,
floating precision, or annotation dtypes.

`AnnotationDataset` and `StreamingAnnotationDataset` remain optional consumers
of the existing stem-matched payload. Their default output is a CHW image tensor
plus loaded Annotation objects. TorchVision decoding preserves channel count
and supported source bit depth, including grayscale/RGBA and uint16 PNG; RGB
conversion, scaling, and normalization require the selected processor. `target_transform` selects an existing
conversion when a consumer needs tensors. These are the retained project
dataset implementations; native library datasets remain selectable through Hydra.

Labeled inference uses `Predictor.predict_dataset`: it yields native
predictions alongside original targets without forwarding labels into the
model. Pair batches use indices zero and one. Other batch containers select
inputs/targets explicitly through Hydra-instantiated standard callables, such
as `operator.itemgetter` or `operator.attrgetter`. Input-only streams continue
using `predict_batches`. See [Inference](inference.md).

~~~folder
datasets/<dataset>/<artifact>/
├── payload/
│   ├── images/
│   └── annotations/
└── dataset-artifact.json
~~~

The dataset-only bucket is the source for Dataset Artifacts. Its Terraform root
is [`feral-vision/terraform/buckets/dataset/`](../../feral-vision/terraform/buckets/dataset/). It has
Object Versioning off, a 7-day soft-delete window, Object Retention Lock
enabled, and least-privilege access for the Cloud Build publisher and training
readers. General storage must not be a source for a Dataset Artifact.

`dataset-artifact.json` lists every payload file with its SHA-256 and Cloud
Storage generation. The publisher writes each object once with
`if_generation_match=0` and sets Unlocked object retention on it, so a published
generation cannot be replaced or deleted before its retain-until time.

GPU training does not run DVC. The training VM stages the published payload and
the exact `dataset-artifact.json` onto its local SSD and records that manifest's
SHA-256 in MLflow lineage and terminal training evidence. See the
[Dataset Artifact boundary](cloudops.md#dataset-artifact-boundary). Do not write
run evidence back over a reviewed training input in place. A missing or
malformed `dataset-artifact.json`, or a missing pinned annotation generation,
fails deployment preflight.

## Acquisition and publication

An acquisition image is source-specific. It writes a canonical
`/workspace/payload/images/` and `/workspace/payload/annotations/` layout. The
publication image validates this shared workspace, uploads the payload and
`dataset-artifact.json` with object retention, and prints the artifact URI.

Every publication supplies immutable acquisition and DVC image digests and a
new, reviewed `DATASET_ARTIFACT_PREFIX`. The prefix is intentionally a required
build substitution: a rerun must choose a new artifact prefix rather than
overwrite a training input. New download sources implement this workspace
layout without adding their download libraries to the publication image.

Publication scripts and the publication API require `GCS_URI_PREFIX` in the
environment. Cloud Build supplies it through `_GCS_URI_PREFIX`. The bucket URI
remains in `TRAINING_DATA_BUCKET_URI`; no URI prefix is hard-coded.

## Dataset tracking boundary

Scripts and source adapters own acquisition, conversion, and augmentation.
DVC registers exactly one prepared Dataset at a time; a Variant follows the
same registration contract as a raw Dataset. The previous `dvc.yaml` and
former `scripts/data/acquire.sh`, `process.sh`, and `common.sh` were removed because
they imposed a fixed stage graph that did not match the producers. Existing
Dataset files were preserved. Do not recreate broad ownership of `feral-vision/data/raw`,
`feral-vision/data/processed`, or `feral-vision/data/augmented`.

Use `feral-vision/scripts/data/register.sh DATASET_ROOT` from the selected DVC repository,
with DVC available on PATH and a default remote configured. It checks repository
containment and the two Dataset directories, then runs `dvc add` and a targeted
`dvc push`. It does not validate annotations or provenance, run acquisition,
synchronize unrelated data, publish the retained manifest, or create `dvc.lock`.
The producer must validate its Dataset before registration. Select independent,
non-overlapping Dataset roots; retain the generated sibling `.dvc` metadata and
Git ignore changes in Git. Ignore rules allow these metadata files under
`data/` without including data files.

Configure the existing dataset-only bucket's `/dvc` prefix as the default remote
in `.dvc/config.local`; no unexpanded bucket variable is stored in tracked
configuration. The [Dataset guide](../guide/dataset.rst) is the operator
reference for complete commands, inputs, outputs, credentials, and official DVC
references. Registration/recovery has been checked against a filesystem remote;
that is not proof of cloud permissions or existing cloud data.

## Remaining publication gaps

- `feral-vision/deploy/cloudbuild.prepare.yaml` still calls the retained payload/manifest
  publisher without DVC registration. Connect its exact Dataset to a durably
  preserved `.dvc` record and source/operation provenance. This is upstream work;
  GPU training must continue consuming the published manifest without DVC.
- `publish_dataset_artifact` checks directories and basic metadata, not
  annotation semantics, non-empty payloads, or full provenance.
- `feral-vision/scripts/cloud/materialize_detection_variant.sh` imports an absent Variant
  publisher. Its YOLO output conflicts with preflight/startup's pinned COCO
  `instances.json` requirement. Resolve the seam before claiming GPU readiness.

The publication Dockerfile is
[`feral-vision/deploy/dataset-publisher/Dockerfile`](../../feral-vision/deploy/dataset-publisher/Dockerfile).
It has no `.dvc` suffix, so DVC does not mistake it for tracking metadata.
