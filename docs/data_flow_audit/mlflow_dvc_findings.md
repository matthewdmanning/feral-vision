# MLflow and DVC: findings

Checked 2026-10-15. Scope: official MLflow documentation and MLflow source,
with the project lifecycle in [instructions.md](instructions.md) and
[data_flow_reference.md](data_flow_reference.md) as context. This is research,
not a selected implementation or an executable workflow.

## Finding

**The user clarified that the artifact being logged is a DVC output.** The
relevant MLflow interface is therefore artifact logging: `mlflow.log_artifact`
accepts a local file or directory and saves it with the run. It does not
prescribe the file's internal DVC format, `.dvc` versus `dvc.lock`, or a record
granularity. Logging a DVC output as an artifact does not require converting it
to an `mlflow.data.Dataset` object. Dataset input logging is a separate API,
documented below only to distinguish the interfaces.
[Dataset input API](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.html#mlflow.log_input),
[artifact API](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.html#mlflow.log_artifact).

The user's phrases about records describe the desired training-data reference;
they do not prescribe a record format or granularity. No such requirement is
inferred here.

**Qualification after the user's association check:** accepting a DVC output as
an MLflow artifact is not proof that it describes the data actually supplied to
training. That association must be established separately. See
[the example investigation](mlflow_dvc_examples.md) for external evidence and
its limits.

## What MLflow accepts and records

| Interface | Accepted input and recorded result | DVC implication |
| --- | --- | --- |
| `mlflow.log_input(dataset, context, tags)` | An `mlflow.data.dataset.Dataset` object, with optional usage context and input tags, associated with the current run. | A `.dvc` pathname is not this API's dataset argument. |
| `Dataset` serialization | Name, digest, source type, and serialized source; optional schema and profile when supplied by the dataset implementation. | Relevant only if a separate structured dataset input is logged; not a prerequisite for logging the DVC output artifact. |
| `mlflow.log_artifact(local_path, ...)` | A local file or directory saved as a run artifact. | A staged `.dvc` file can be preserved as a file; this does not itself create a structured dataset input. |

These contracts are confirmed in the project's locked MLflow version, 3.14.0:
[input creation and logging](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/tracking/fluent.py#L1331-L1380),
[dataset serialization](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/dataset.py#L34-L47),
[artifact logging](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/tracking/fluent.py#L1513-L1544).
The version was read from the local [lockfile](../../uv.lock).

`MetaDataset` is a metadata-only dataset implementation available in 3.14.0.
It accepts a `DatasetSource`, optional name, optional digest, and optional
schema. Its default digest hashes metadata rather than image or annotation
contents. This is an available interface, not a recommendation to adopt its
default identity for the project.
[MetaDataset source](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/meta_dataset.py).

### MetaDataset details and lifecycle relevance

`MetaDataset(source, name=None, digest=None, schema=None)` accepts a
`DatasetSource` and optional descriptive fields. Logging it with `log_input`
records dataset metadata as a run input; it does not upload the image/mask
payload or attach the DVC output file. See the
[official dataset guide](https://mlflow.org/docs/latest/ml/dataset/).

In 3.14.0, the default digest is the first eight hexadecimal characters of a
SHA-256 over name, serialized source, source type and schema. It does not hash
the data bytes. The inherited default name is `dataset`, despite the
MetaDataset docstring's suggestion that a name is generated.
[MetaDataset implementation](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/meta_dataset.py),
[base Dataset implementation](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/dataset.py).

Project implication: this could record a reference to the registered GCS data
within the training run, alongside separately logged DVC output. It neither
verifies the loader's inputs nor automatically supplies parent or inference-model
lineage. Its default name/digest is not a demonstrated implementation of the
user's one-to-one identity requirement. No integration has been selected or run.

## DVC-specific support and GCS references

The 3.14.0 dataset-source registry explicitly registers generic artifact sources,
HTTP, Hugging Face, Spark, Delta, code, UC volumes, and Databricks evaluation
sources. It also loads external `mlflow.dataset_source` plugin entrypoints.
There is no DVC-specific source registered in this inspected file. This does
not rule out external plugins or project code.
[Source registry](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/dataset_source_registry.py).

Generic artifact-backed dataset sources store a URI and can explicitly load it
through MLflow artifact downloading. The artifact registry includes the `gs`
scheme, so a GCS reference has a generic source representation. That machinery
does not interpret DVC catalogue contents or recover parent/model provenance
from a DVC file.
[Artifact dataset sources](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/artifact_dataset_sources.py),
[artifact repository registry](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/store/artifact/artifact_repository_registry.py).

## Relevance to this project's data flow

For acquisition/registration, optional augmentation with a parent link, GCS
storage, and copying data plus required DVC files to ephemeral GCE, the relevant
integration boundary is logging the staged DVC output as a run artifact.
MLflow's artifact interface accepts that local output without imposing a DVC
schema. Which DVC output the project selects and how training invokes artifact
logging remain implementation questions, not additional user requirements.

Saving a DVC metadata file can preserve the catalogue evidence received by the
GCE job. Structured input logging can associate dataset metadata with the run.
Neither operation alone demonstrates that root sources, augmentation parents,
or inference model identities remain locatable. That must be assessed against
the registered references and the actual data supplied to training; content
hashes alone do not establish the lineage required by the user.

No format, per-file DVC layout, `dvc.lock` requirement, staging protocol, or
automatic metadata consumer has been selected by this investigation.

## Follow-up: association in the inspected project code

Read-only source inspection found the following:

- [`publish_dataset_artifact`](../../src/feral_vision/data/dataset_artifact.py)
  generates `dataset-artifact.json` itself from supplied metadata, payload file
  names, SHA-256 values and GCS generations. It does not invoke DVC or derive
  that record from a DVC output in the inspected function.
- [`_try_log_dataset_lineage`](../../src/feral_vision/training/trainer.py)
  resolves that manifest from `DATASET_ARTIFACT_MANIFEST` or configuration,
  checks its hash against an expected value when supplied, and logs the
  manifest, hash and optional URI to the current MLflow run. This attaches the
  custom manifest to the run; it is not logging a DVC-generated record.
- [`container_train.sh`](../../scripts/runs/container_train.sh) checks the
  manifest hash and passes `TRAIN_DATA` as `data.root`; the trainer entrypoint
  constructs its loader from that root. The manifest path is supplied
  separately. The inspected code does not compare the files read by the loader
  with a DVC record.
- [`fit`](../../src/feral_vision/training/trainer.py) also accepts a dataloader
  independently of the configuration used to resolve the logged manifest.
  Consequently, attachment to the same run alone does not prove that a chosen
  DVC output matches the data consumed by that loader.

**Result:** the required DVC-output association is not verified for this project
by the inspected path. This is a bounded source inspection, not a full audit or
a runtime result. No implementation was changed.

## Search coverage and limits

- Searched official MLflow pages for `DVC` and `Data Version Control`; results
  did not yield a DVC-specific file-consumption contract. These are search
  findings, not proof that no mention exists anywhere on the site.
- Searched the opened latest `mlflow` and `mlflow.data` API reference pages
  for `DVC`; neither contained the term. The relevant input and artifact
  contracts were then checked against tagged 3.14.0 source.
- The versioned 3.14.0 HTML API URL was inaccessible through the browsing tool;
  tagged official source supplied version-specific evidence instead. Latest
  documentation is mutable and is not assumed to match every pinned behavior.
- No third-party integration or DVC cookbook was adopted. No DVC, MLflow,
  training, or cloud trial ran. Installed plugins were not audited; the later
  source inspection above covers only the specified publication/training path.
  No guide changes are needed for this research-only document.

## Mapping DVC outputs to MetaDataset

**Yes: DVC metadata plus the known registered storage location provides enough
information to construct a metadata-only MLflow input.** A `.dvc` file alone
does not necessarily contain that storage URL. This mapping is an available
integration, not a selected project schema.

MLflow 3.14.0 requires a `DatasetSource` object for `MetaDataset.source`;
`name`, `digest`, and `schema` are optional. A raw DVC dictionary is not that
source object. [Constructor](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/meta_dataset.py#L54-L64).

| MetaDataset input | Information available |
| --- | --- |
| `name` | DVC `outs.path` provides a tracked name/path; the registered dataset identifier can instead supply the name. Choosing the latter's mapping is project policy. |
| `digest` | DVC's output MD5 can be supplied without recomputing the image/mask contents. |
| `source` | Use the registered GCS location, or resolve the DVC remote location using metadata and configuration. `outs.path` is normally relative to `wdir`; `outs.remote` is a remote name, not necessarily its URL. |
| `schema` | Ordinary DVC records do not supply an MLflow image/mask schema. This is optional, so its absence does not block construction. |

[DVC output specification](https://doc.dvc.org/user-guide/project-structure/dvc-files#output-entries),
[DVC URL resolution API](https://doc.dvc.org/api-reference/get_url).
The GCS source implementation accepts `uri`, serializes it as `{"uri": ...}`,
and reports source type `gs`; it can be obtained through MLflow's source
resolver. [Generic source implementation](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/artifact_dataset_sources.py#L63-L147),
[GCS registration](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/store/artifact/artifact_repository_registry.py#L105-L112).
Resolving a directory's DVC remote URL identifies its index object; it does
not make MLflow interpret that object as an image directory.

Full 32-character MD5 and 36-character `<md5>.dir` values fit MLflow 3.14.0's
36-character digest limit. Its validator applies no hexadecimal-only rule;
the base class's 8–10-character guidance is a recommendation, not that limit.
[Validation](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/utils/validation.py#L697-L732),
[digest limit](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/utils/validation.py#L61-L62),
[base class](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/dataset.py#L23-L30).

A directory's `.dir` index supplies individual relative paths/hashes, not an
MLflow schema. Import `deps`, when present, can supply source references;
ordinary `dvc add` does not create them.
[Directory index](https://doc.dvc.org/user-guide/project-structure/internal-files#directories),
[import dependencies](https://doc.dvc.org/user-guide/project-structure/dvc-files#dependency-entries).

Constructing this object and logging the staged DVC output are separate from
verifying that the GCE loader consumed its referenced files. Neither establishes
source/parent/inference-model lineage automatically. No trials ran for this
mapping; the conclusion follows the cited format and API contracts.

### Schema mapping and paths on ephemeral GCE

`MetaDataset.schema` describes the dataset's structure using MLflow column or
tensor specifications. It does not rename DVC metadata fields or populate the
`source`, `name`, and `digest` constructor arguments. Those values must be
extracted and supplied separately. A project-defined mapping could do this;
it is not the role of the MLflow `schema` argument.
[MLflow schema types](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.types.html),
[MetaDataset implementation](https://github.com/mlflow/mlflow/blob/v3.14.0/mlflow/data/meta_dataset.py).

DVC `outs.path` is relative to its working directory, which defaults to the
tracking file's directory. Preserving that relative layout when copying data
and metadata to GCE can make the record resolve to the training copy. A local
symlink can also resolve to the staged files while that target exists; it does
not prove their contents match the record.
[DVC path specification](https://doc.dvc.org/user-guide/project-structure/dvc-files).

Against this project's requirements, that local resolution addresses access to
the staged training data, not the complete source/lineage relationship. Because
GCE is ephemeral, a GCE-only path or symlink cannot be the only means of finding
the root sources and lineage. The registered identifier must still resolve to
those through retained records. This does not require embedding a GCS URI or
all lineage details in every DVC file. No path layout or symlink behavior was
trialled for this comparison.
