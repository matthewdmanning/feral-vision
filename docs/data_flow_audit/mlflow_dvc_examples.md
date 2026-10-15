# DVC output associated with MLflow training: external examples

Checked 2026-10-15. Context: registration, optional augmentation with a parent
link, GCS storage, copying data and required DVC files to ephemeral GCE, and
recording the data used by training in MLflow. This research evaluates
association mechanisms; it does not adopt example workflows or add project
requirements. Current-project verification is separate from these examples.

## Strong example: AWS sample training source

[Official AWS example](https://github.com/aws-samples/sample-amazon-sagemaker-mlflow-dvc-lineage/blob/main/source_dir/train.py):

1. `fetch_data_from_dvc()` clones the data repository at the selected tag,
   obtains its actual Git commit, and runs checked `dvc pull` in that repository
   (lines 88–108).
2. `DATASET_PATH` points into that same checkout. `ImageFolder` reads its
   `train` and `validation` subdirectories (lines 44–45, 237–244).
3. Inside the active training run, MLflow logs the returned commit and data
   repository URL as parameters. If present, `dataset/manifest.csv` is saved as
   an artifact (lines 253–277).
4. The resulting datasets feed the data loaders and training loop, and the
   model is logged within that run (lines 279–364).

**Association verified by source inspection:** repository revision → restored
data → loaders → model/run. This records a reference to DVC metadata in Git;
it does not upload `.dvc` as an MLflow artifact. The optional manifest comes
from the restored dataset. Its rows are not independently compared with
`ImageFolder` membership. There is no explicit post-copy content rehash in the
trainer. Runtime image transforms are applied; the recorded dataset identifies
their input, not each transformed tensor. No example execution was performed.

SageMaker initiates training; the inspected script uses DVC for retrieval, not
`dvc repro`, `dvc exp run`, or a DVC training stage. The associated
[AWS article](https://aws.amazon.com/blogs/machine-learning/end-to-end-lineage-with-dvc-and-amazon-sagemaker-ai-mlflow-apps/)
assigns processing/training orchestration to SageMaker and dataset versioning
to DVC. Its AWS infrastructure and domain-specific manifest are not project
requirements.

## Exact pointer-file logging example, with an important gap

[Hidacs author tutorial, section 7](https://hidacs.ch/en/blog/mlops-setup/#7-log-dataset-version-during-training)
opens `dataset.dvc`, parses its first output hash, optionally resolves
`dataset/` through `dvc.api.get_url`, and logs that hash, URL, Git commit, and
`dataset.dvc` into the same MLflow run.

This directly demonstrates preserving **DVC command output as an MLflow
artifact**, alongside extracted references. DVC does not initiate training in
the shown example. However, the snippet has no data-loading or model-fitting
call and logs a fixed accuracy value. It therefore demonstrates the logging
mechanism, **not verified correspondence with consumed training data**. It
does not recompute data hashes or establish source/parent/model lineage.
Its fallback values and unrelated setup instructions have not been adopted.

## Supporting example: training-data reference logging

[The Pragmatic Programmer for Machine Learning, sections 12.4.2–12.4.3](https://ppml.dev/nlp.html#training-and-experiment-tracking)
describes retrieving a selected corpus revision through `dvc.api.get_url`,
feeding the corpus to Word2Vec, and using MLflow parameters to record its DVC
path/hash and query metadata. The displayed workflow launches a training
script directly after `dvc pull`; DVC does not orchestrate training.

This supports the reference-logging approach. Its displayed MLflow snippet
omits the actual DVC path/hash logging calls, so it is weaker evidence than
the AWS source. It also says `dvc pull` retrieves corresponding metadata;
that statement was not accepted as command-behavior evidence. The example
does not demonstrate logging the `.dvc` file itself.

## Rejected or unavailable examples

- [Emily template](https://emily.ambolt.io/docs/v3.0.4/guides/dvc-mlflow-template):
  explicitly starts experiments through a DVC pipeline containing a training
  stage. Excluded from candidate workflows.
- [Computer-vision tutorial](https://theja-vanka.github.io/blogs/posts/deployment/github-mlflow/#dvc-mlflow-integration):
  its standalone snippet hashes a `dvc.lock` path and logs `data.dvc`, but
  does not demonstrate their relationship to the actual loader. The captured
  `dvc data status` output is unused. Excluded as association evidence.
- [SURF tutorial](https://servicedesk.surf.nl/wiki/spaces/WIKI/pages/35586110/Reproducible%20machine%20learning%20with%20DVC%20mlflow):
  the detailed fetch returned HTTP 401. No conclusions rely on its unavailable
  content.

## Project relevance and remaining verification

The useful distinction is between **logging a metadata file** and **showing
that its referenced data entered the training loader**. The AWS code traces
that relationship; the pointer-file snippet alone does not. Neither example
establishes that this project's staged files and MLflow run are already linked.

For this project, any conclusion must follow the registered DVC output through
GCS, the copy to GCE, the selected loader inputs, and the MLflow evidence. A
logged hash or filename alone cannot demonstrate that whole association or
the required source/parent/inference-model lineage. This is the scope of
verification against the user's lifecycle, not a chosen schema or a demand
that DVC drive training.

No external code was executed, no cloud calls or trials ran, and no example
was adopted wholesale. Source links using `main` and tutorial pages are mutable.
