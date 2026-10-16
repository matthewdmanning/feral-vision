# DVC data flow audit: cloud handoff

Prepared 2026-10-15. **Transfer has not occurred.** The originating session had
the cloud-environment runtime skill but no callable environment-status or cloud
handoff tool. No managed environment readiness was established.

## Read first

1. [User instructions](instructions.md): authoritative requirements, exact
   lifecycle, clarifications, trial rules, and document location.
2. [Agent data flow draft](data_flow_reference.md): acquisition/registration,
   optional augmentation with parent reference, GCS storage, copying data and
   required DVC files to ephemeral GCE in the same region, and MLflow recording.
3. [Command investigation](dvc_commands.md): DVC 3.67.1 inputs, outputs, tested
   options, metadata examples, and the project JSON manifest comparison.
4. [MLflow findings](mlflow_dvc_findings.md): pinned 3.14.0 API contracts,
   MetaDataset mapping, source inspection, and limits.
5. [External examples](mlflow_dvc_examples.md): distinguishes artifact logging
   from evidence tying the recorded dataset version to the training loader.

## Current understanding

- Existing repository documentation can be wrong. Analyze all evidence against
  the user's instructions and lifecycle. Do not add requirements or replace
  descriptive wording with new record-granularity requirements.
- DVC outputs can supply names/paths and hashes for MetaDataset. Its required
  source object needs the registered storage location or DVC remote context.
  Its optional schema describes data structure; it does not map metadata fields.
- Relative paths can preserve access to staged data. A path or symlink existing
  only on ephemeral GCE cannot be the only way to locate root sources and
  lineage. Identifier resolution may use retained catalogue references; no rule
  requires all relationship details in each DVC file.
- Attaching a file to an MLflow run does not establish that it describes the
  data actually consumed. The inspected trainer logs a custom
  `dataset-artifact.json`; its association with a DVC-generated output is not
  verified.
- No DVC training orchestration has been adopted. The user explicitly excluded
  examples that use DVC to drive training.

## Completed trials and limits

The bounded local DVC trials used copied `data/augmented/` under project-root
temporary folder UUID `428536a1-c4df-42c6-b676-a08b1e91a9fb`. The folder, logs,
and local ignore entry were deleted after verification; results remain in the
command document. Original data was verified unchanged. The copy contained
72 images and 64 masks; eight motion_blur images lacked same-stem masks. No
alternative pairing was inferred.

No MetaDataset integration, relative-path/symlink trial, cloud transfer, or
end-to-end training validation has been performed. No final implementation was
selected. The latest user questions concern schema mapping and whether staged
paths/symlinks satisfy the lifecycle; the findings document records the
API-based answer and distinguishes it from execution evidence.

## Resuming in the cloud

Read the invoked cloud-environment runtime skill and obtain current environment
status through its supported tool before treating an environment or identity as
ready. Do not reuse assumed instance IDs or credentials. Follow the user's
trial rules before any new trial, including a new unique identifier stored in
memory and cleanup after completion. Keep authored documents in this folder.

These files must reach the cloud workspace before this handoff is effective.
No commit, push, upload, or session transfer was performed by preparing this
document.
