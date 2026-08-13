# 2026-08-07 first_run_augmented storage state

## Dataset Artifact identity

The dataset-only bucket is `gs://mobile-training-images`. For this run, the
published raw Dataset Artifact is:

`gs://mobile-training-images/datasets/coco/train2017/raw-20260806-800-animals-v2/`

Its storage layout is:

```text
payload/images/
payload/annotations/
dataset-artifact.json
dataset-artifact.dvc
```

`dataset-artifact.dvc` is the existing DVC Dataset Artifact tracker under that
raw `v2` prefix. Consume that tracker to obtain the DVC-pinned payload; do not
create another tracker or republish the raw Dataset Artifact.

## Confirmed current state

- The COCO `train2017` payload has both `images/` and `annotations/`.
- `dataset-artifact.json` and `dataset-artifact.dvc` exist under the raw `v2`
  prefix.
- The raw `v2` Dataset is the narrowed full COCO `train2017` Dataset for the
  selected 10 classes. `dataset-artifact.json` is its manifest.

## Storage boundaries

- `gs://mobile-training-images/` is the Dataset Artifact catalog and the only
  bucket whose object versions DVC pins.
- `GCS_BUCKET` names that dataset-only bucket for data publication and
  materialization scripts.
- `MLFLOW_ARTIFACT_PREFIX` is separate operational storage for Run Records; it
  must not be a prefix in `gs://mobile-training-images/`.
- Terraform state uses separate protected operations storage; it is not a
  Dataset Artifact location.

## Next read-only acceptance check

Read the published `dataset-artifact.dvc` and confirm its DVC `version_id`
selects the payload object generation. Report that tracker generation and the
manifest-defined logical payload, rather than an unversioned bucket listing.
