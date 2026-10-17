# Train a model and preserve its outputs

Use the container runner to train with a selected Hydra configuration and save
run outputs, including logs, in the existing Cloud Storage bucket. Each attempt
has its own folder under the VM's numeric instance ID.

The VM and container are the starting point. Terraform and Docker setup remain
in the [preserved setup reference](reference/2026-10-17-google-cloud-review.md).
The existing detection deployment does not select this runner automatically.

## Prepare the inputs

Assume the data, model files, DVC files and configs already exist in the bucket.
Download the files needed for the selected run using Google SDKs or `gcloud`,
keeping the layout expected by the config. Complete those downloads before
starting the runner; the runner does not download inputs or create resources.

DVC files are existing inputs. Copy them unchanged; this training script adds
no DVC commands, registration, publication or catalogue workflow.

Select a complete training config using the contracts in
[`src/sightkit_learn/config/`](../../src/sightkit_learn/config/).
`feral-vision/conf/` is a collection of configurations previously tried. The
runner uses the selected config as written, with **no Hydra overrides**.

## Run inside the prepared container

The container needs `sightkit_learn`, the runner files and access to the Compute
Engine metadata server. Its VM identity must be able to read and write the
selected output location, including reading object metadata for verification.

Export these environment variables:

| Variable | What to supply |
| --- | --- |
| `CONFIG_DIR` | Absolute local directory containing the downloaded Hydra configs. |
| `CONFIG_NAME` | Name of the selected Hydra config, without `.yaml`. |
| `RUN_OUTPUT_DIR` | Local workspace for this attempt's outputs. Use a fresh directory and keep input data separate. |
| `TRAINING_DATA_BUCKET_URI` | Existing Cloud Storage bucket URI or bucket prefix for the outputs. Despite its name, this variable selects the runner's output destination. |

Then, from the repository root, run:

```bash
bash feral-vision/scripts/runs/cloud_train.sh
```

The script runs from `RUN_OUTPUT_DIR`. Relative paths in the config resolve
there. Configured absolute checkpoint and local tracking paths outside that
workspace are also collected; the config is not rewritten. Output symlinks
are rejected, and an in-memory SQLite tracking database is not supported.

The training work stays in the library:

```python
trainer = build_trainer(cfg)
train_loader = build_dataloader(cfg)
history = trainer.fit(train_loader)
```

Hydra supplies `cfg` as an OmegaConf `DictConfig`. The runner saves the returned
`history`; it does not implement another training loop.

## Find the outputs

The runner prints the full destination and records it in `console.log`:

`<TRAINING_DATA_BUCKET_URI>/instances/<instance-id>/<attempt-id>/`

The instance ID comes from Compute Engine metadata. A new attempt ID prevents
later runs on the same VM from overwriting an earlier run. Paths below are
relative to this cloud folder.

| Output | Location |
| --- | --- |
| Combined stdout/stderr, including library logging and Python tracebacks | `console.log` |
| Resolved Hydra config used for the run | `resolved-config.yaml` |
| Best model weights | The path selected by `cfg.train.best_model_path` |
| Returned per-epoch metrics and best monitored value | `history.json`, after successful training |
| Local MLflow tracking database and artifact files | Their paths within the output workspace |
| MLflow run metadata and metric histories | `mlflow-export/run.json` |
| MLflow run artifacts, including logged config and any supplied lineage | `mlflow-export/artifacts/` |
| Native MLflow model packages | `mlflow-export/models/<model-id>/` |
| Registered model version metadata, when created | `mlflow-export/model-version.json` |
| Original locations of collected outputs outside the workspace | `output-sources.json` |
| Other files created in the output workspace | Their existing relative paths |
| Final training exit code and output URI | `output-status.json`, uploaded last |

Files collected from outside the workspace appear under
`external/<absolute-path-without-leading-slash>/`. This applies to configured
absolute checkpoint and local tracking paths. MLflow exports are produced when
a run exists; they do not replace the configured tracking backend.

`history` is a Python dictionary returned by `Trainer.fit`, not a separate
tracking service. The ordinary library CLI discards it; this cloud runner saves
it. Checkpoints contain model weights, not full optimizer/scheduler resume state.

## Completion and failures

The runner exports files periodically, waiting 30 seconds between export cycles.
It verifies each snapshot's uploaded size and MD5 and reuses unchanged objects.
SQLite's backup API preserves committed data, including committed WAL records,
without relying on a raw copy of an open database. Checkpoint writes atomically
replace the previous weights so a failed save leaves the previous file intact.

When training ends, the runner stops periodic export, drains captured logs and
performs a final export. It publishes `output-status.json` only after those
uploads verify. Local originals remain available for recovery.

| Result | What it means and what to do |
| --- | --- |
| Exit code `0` and terminal record with `training_exit_code: 0` | Training and final export succeeded. Outputs are archived. |
| Nonzero training status with an uploaded terminal record | Training failed, but the final export succeeded. Inspect the archived logs and available outputs before cleanup or a new attempt. |
| Final export fails | The runner returns failure. Do not treat the attempt as complete until its uploads and terminal record are verified. Keep the VM and local workspace; inspect `console.log` and local `export-errors.log` before recovering the export. |
| SIGTERM or SIGINT | The runner stops the training process group, then attempts final export. Shutdown grace must allow export to finish. |

VM cleanup belongs to the caller. Wait for verified output preservation before
normal cleanup; a running VM or a zero training-process exit code alone does
not establish that outputs reached the bucket. Rerunning the training script
starts a new attempt; it is not an export-only retry or checkpoint resume.

**Forced VM destruction is an accepted data-loss case.** It cannot execute
final cleanup. Only uploads already completed in Cloud Storage are assumed to
survive; no recovery-time guarantee is claimed for that case.

## What has been verified

[The 14-case preservation suite](../../tests/test_cloud_run_outputs.py) checks
retained bytes and restored behavior, including:

- Real Hydra/PyTorch/MLflow training, parameter updates, and restoration after
  deleting the original workspace, using both relative and absolute paths.
- Equality of restored model weights and metric values with the training outputs.
- Captured stdout/stderr, failed training, SIGTERM, upload failure and checksum mismatch.
- Committed SQLite WAL data, unique VM/attempt destinations, periodic updates
  and recovery from a transient upload failure.
- A partial checkpoint write that fails without destroying the previous weights.

Controlled mutations confirmed that removing atomic checkpoint replacement or
disabling periodic export makes the targeted tests fail. Automated tests mock
the Google SDK transport. A separate SDK upload and byte-for-byte download check
passed against the configured existing bucket; its tiny validation object was
retained.

These checks used an isolated CPU environment. No VM/GPU deployment, image
rebuild or switch of the existing detection deployment was performed.

Implementation: [shell runner](../../feral-vision/scripts/runs/cloud_train.sh)
and [output helper](../../feral-vision/scripts/runs/run_outputs.py), mirrored in
`src/templates/scripts/runs/`.
