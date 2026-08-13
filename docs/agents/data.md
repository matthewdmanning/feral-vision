# Data and ingestion

Use this guide when changing data ingestion, dataset contracts, or dataset
publication. Data operation entrypoints live in
[`scripts/data/`](../../scripts/data/).

## Data flow

`Data Source Adapter -> request -> optional transform or format -> Dataset`

`Dataset -> modification -> Dataset Variant`

`Dataset or Dataset Variant -> Publish -> DVC Registry`

A Dataset Variant is a Dataset. DVC owns Dataset Artifacts and their lineage.

Every dataset root has `images/` and `annotations/` directories. Annotation
files match image stems: masks use `.png` or `.jpg`, YOLO boxes use `.txt`, and
classification labels use `.json`; `names.yaml` records class indices. The data
source dispatch in `data/fetch.py` must resolve every source to this layout.

~~~folder
datasets/<dataset>/<artifact>/
├── payload/
│   ├── images/
│   └── annotations/
├── dataset-artifact.json
├── dataset-artifact.dvc
└── dvc.lock
~~~

The dataset-only bucket is the source for Dataset Artifacts and is the only
bucket whose object versions DVC pins. It has Object Versioning, dataset-specific
lifecycle rules, and least-privilege access for the Cloud Build publisher,
DVC-repository automation, and training readers. General storage must not be a
source for a Dataset Artifact.

Cloud Build records each prepared `payload/` folder with DVC. The DVC remote
stores the Dataset's managed data and the Dataset Artifact prefix receives only
the resulting `dvc.lock`. The temporary no-SCM DVC workspace runs `dvc add`,
defines the Dataset folder as a stage dependency, runs `dvc repro`, and pushes
the DVC-managed Dataset. Object Versioning must be enabled on the source bucket
before this workflow is used.

`dvc.lock` records the selected Dataset folder. The training VM stages its
selected data on the local SSD, runs DVC there before model training, and
records the resulting lock digest in MLflow lineage. Do not write that local
run evidence back over a reviewed training input in place.

### Uncommitted tracker recovery

`dataset-artifact.dvc` without `dvc.lock` is uncommitted source metadata, not
training lineage. The training VM creates its own local DVC workspace after
staging the canonical payload. If that workspace already has `.dvc` without
`dvc.lock`, it runs `dvc commit`, reproduces the Dataset stage with `dvc repro`,
and verifies the local lock before training. Do not infer a lockfile from a
`.dvc` tracker or overwrite the source artifact with run-local metadata.

## Acquisition-publication contract

An acquisition image is source-specific. It writes a canonical
`/workspace/payload/images/` and `/workspace/payload/annotations/` layout. The
DVC publication image validates this shared workspace, records the folder with
DVC, runs `dvc repro`, pushes the DVC-managed Dataset, and publishes `dvc.lock`.

Every publication supplies immutable acquisition and DVC image digests and a
new, reviewed `DATASET_ARTIFACT_PREFIX`. The prefix is intentionally a required
build substitution: a rerun must choose a new artifact prefix rather than
overwrite a training input. New download sources implement this workspace
contract without adding their download libraries to the DVC image.
