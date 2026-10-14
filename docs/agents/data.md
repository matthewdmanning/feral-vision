# Data and ingestion

Use this guide when changing data ingestion, dataset layout, or dataset
publication. Data operation entrypoints live in
[`scripts/data/`](../../scripts/data/).

## Data flow

`Data Source Adapter -> request -> optional transform or format -> Dataset`

`Dataset -> modification -> Dataset Variant`

`Dataset or Dataset Variant -> Publish -> Dataset Artifact`

A Dataset Variant is a Dataset. The `dataset-artifact.json` manifest owns the
file list of a Dataset Artifact.

Every dataset root has `images/` and `annotations/` directories. Annotation
files match image stems: masks use `.png` or `.jpg`, YOLO boxes use `.txt`, and
classification labels use `.json`; `names.yaml` records class indices. The data
source dispatch in `data/fetch.py` must resolve every source to this layout.

~~~folder
datasets/<dataset>/<artifact>/
├── payload/
│   ├── images/
│   └── annotations/
└── dataset-artifact.json
~~~

The dataset-only bucket is the source for Dataset Artifacts. Its Terraform root
is [`terraform/buckets/dataset/`](../../terraform/buckets/dataset/). It has
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
