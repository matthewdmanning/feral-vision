# Data and model tests

Use this guide when changing data ingestion, datasets, model tests, or model
examples.

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
└── dataset-artifact.dvc
~~~

The dataset-only bucket is the source for Dataset Artifacts and is the only
bucket whose object versions DVC pins. It has Object Versioning, dataset-specific
lifecycle rules, and least-privilege access for the Cloud Build publisher,
DVC-repository automation, and training readers. General storage must not be a
source for a Dataset Artifact. Keep Terraform state in a dedicated protected
operations bucket with Cloud Build staging when their prefixes have separate,
least-privilege IAM conditions; both remain separate from datasets.

Cloud Build publishes prepared data to a versioned Cloud Storage prefix. The
dataset bucket is the Dataset Artifact catalog: each artifact prefix contains a
`payload/` directory, `dataset-artifact.json`, and a version-aware
`dataset-artifact.dvc` tracker. Cloud Build creates that tracker with
`dvc import-url --no-download --version-aware` after publishing the payload.
The temporary no-SCM DVC workspace exists only to generate the tracker; it does
not store dataset blobs or become a training dependency. Object Versioning must
be enabled on the source bucket before this workflow is used.

The tracker records the GCS object generations. Training consumes the selected
tracker and staged data, and records the tracker digest in its run manifest and
MLflow lineage. A new cloud version is adopted only by publishing a new artifact
prefix or updating its tracker with `dvc update --rev`; do not overwrite a
reviewed training input in place. Do not run DVC in the training container.

## Acquisition-publication contract

An acquisition image is source-specific. It writes a canonical
`/workspace/payload/images/` and `/workspace/payload/annotations/` layout plus
`/workspace/dataset-input.json`. The input metadata must name the dataset and
source and include a provenance object. The DVC publication image validates this
shared workspace, uploads the payload and manifest through the
Python client, then generates and uploads the version-aware tracker.

Every publication supplies immutable acquisition and DVC image digests and a
new, reviewed `DATASET_ARTIFACT_PREFIX`. The prefix is intentionally a required
build substitution: a rerun must choose a new artifact prefix rather than
overwrite a training input. New download sources implement this workspace
contract without adding their download libraries to the DVC image.
