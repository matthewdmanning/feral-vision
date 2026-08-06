# DVC GCS verification

## Scope

This note records a read-only verification of DVC access to the live raw COCO
payload in the dataset-only bucket. It does not publish a Dataset Artifact or
start Cloud Build.

## Verified evidence

The verified payload is:

`gs://mobile-training-images/datasets/coco/train2017/raw-20260806-800-animals/payload`

In a disposable no-SCM DVC workspace, the following version-aware import
completed successfully:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --project /root/feral-vision --directory /tmp/feral-vision-dvc-gcs-verify-E0cB86 dvc import-url --no-download --version-aware gs://mobile-training-images/datasets/coco/train2017/raw-20260806-800-animals/payload dataset-artifact
```

The generated `dataset-artifact.dvc` is frozen, uses `version_aware: true`,
and contains 801 object `version_id` entries. This proves DVC can resolve the
payload's immutable GCS object generations.

DVC also downloaded and parsed
`payload/annotations/instances.json` through `dvc get-url`. The downloaded
file was 2,997,682 bytes and contained 800 images and 4,487 annotations.

## Current state

**Ready for Cloud Verification.** DVC read access and version-aware import are
verified. The live artifact root currently lists `payload/` and
`dataset-artifact.json`, but not a published `dataset-artifact.dvc` tracker.
The publisher workflow must upload that tracker beside the immutable payload
before this raw Dataset Artifact satisfies the data-publication contract.

## Next action

Run the source-agnostic DVC publisher through the regional Cloud Build
preparation workflow, using immutable, verified acquisition and publisher image
digests plus a reviewed artifact prefix. Then verify the artifact root contains
`payload/images/`, `payload/annotations/`, `dataset-artifact.json`, and
`dataset-artifact.dvc` with `version_id` entries.

## Guide impact

No user-facing guide change is needed. This note records execution evidence;
the canonical data contract remains in `docs/agents/data.md`.
