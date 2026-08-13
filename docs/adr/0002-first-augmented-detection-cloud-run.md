# First augmented detection cloud run

## Status

Accepted for `first_run_augmented`. This decision supersedes the managed,
operator-supplied MLflow-endpoint assumption in the 2026-08-05 cloud handoff.
That handoff remains historical evidence of the earlier failed build attempts.

## Decision

The first augmented detection baseline is a two-stage, run-specific cloud
workflow in `us-east4`:

1. A regional Cloud Build derives an immutable Dataset Variant from the
   immutable raw COCO Dataset Artifact.
2. Terraform creates one private, disposable GPU VM from a reviewed plan. The
   VM stages the selected Variant, starts MLflow locally, runs the Hydra Run
   Recipe, exports the Run Record evidence, and is then eligible for teardown.

The Variant is the only training input. Its source remains unchanged. COCO
boxes are converted while materializing the Variant: `cat` is class `0`; every
other selected animal is class `1` (`not-cat`). Invalid and fully out-of-frame
boxes are excluded. The manifest records the raw-artifact lineage, conversion,
and seeded annotation-aware augmentation recipe.

The VM creates the MLflow tracking URI at runtime as
`http://127.0.0.1:5000`. It is bound to VM loopback and is reached only by the
training container through host networking. Operators do not supply a tracking
URI and this run does not create a shared MLflow service. The VM's local
SQLite tracking store is transient; the completed Run Record, Model Artifact,
checkpoint, metrics, startup log, preflight report, and training evidence must
be exported to a dedicated non-dataset GCS artifact prefix before the VM is
destroyed.

## Architecture and ownership

```text
Raw Dataset Artifact -- Cloud Build --> immutable Dataset Variant + DVC tracker
                                             |
Digest-pinned training image ----------------+-- Terraform plan --> private GPU VM
                                                                    |
                                            Variant staged to SSD --+-- local MLflow
                                                                    |
                                  Hydra Run Recipe + Task Adapter --+-- Run Record + Model Artifact
                                                                            |
                                                              non-dataset GCS artifact prefix
```

| Concern | Owner and boundary |
| --- | --- |
| Dataset payloads, manifests, and version-aware trackers | DVC in the dataset-only catalog (`gs://mobile-training-images/`) |
| Augmentation and class conversion | Run-specific Cloud Build materialization; never the VM startup path |
| Container images | Artifact Registry, addressed by immutable digest |
| VM, network, service identity, state, and lifecycle | Terraform in `terraform/runs/detection_first_run_augmented/` |
| Training selection | Hydra Run Recipe `detection_first_run_augmented` |
| Metrics, parameters, checkpoints, Model Artifact, and Run Record | MLflow; no raw dataset directories are logged |
| Durable training evidence | Dedicated non-dataset GCS artifact prefix |

The invoking human identity is the cloud operator identity. The VM identity is
an existing, explicitly selected Google service account. They are not
interchangeable. Terraform must not create or modify IAM unless that change has
been reviewed and explicitly authorized.

## Run contract

`scripts/cloud/prepare_detection_first_run_augmented.sh` is idempotent at the
completed-stage boundary: it verifies existing raw, Variant, and image-digest
outputs before doing work; writes one immutable run manifest; and generates a
fresh Terraform plan. It never applies that plan.

`scripts/runs/detection_first_run_augmented.sh` accepts only the reviewed plan
and run manifest. It applies that exact plan, follows private-VM startup,
collects the preflight report and training evidence, and does not fabricate
success from VM creation or local validation alone.

Every VM-creation input is immutable or versioned: the training-image digest,
Dataset Variant tracker/reference, Run Recipe, service-account reference, and
run manifest. Secrets and credentials are references held by the runtime; they
do not appear in manifests, plans, logs, or documentation.

## Consequences

- A run is ready for cloud verification only after a reviewed plan references
  a digest-pinned image, immutable Variant, selected VM service account, and a
  writable dedicated MLflow artifact prefix.
- The dataset bucket is never used for MLflow artifacts, Terraform state, or
  general operational storage.
- A failed post-apply run retains evidence first. Destroying the disposable VM
  requires a reviewed destroy plan and explicit authorization.
- The local MLflow URI is intentionally not reusable across runs; comparison
  and recovery rely on the exported durable evidence.

## Related documents

- [Run contract](../runs/first-detection-baseline-first_run_augmented.md)
- [Cloud operations](../agents/cloudops.md)
- [Data and ingestion](../agents/data.md)
- [Program flow](../agents/program-flow.md)
