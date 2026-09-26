# Terraform GPU deployment preflight

This directory contains the **pre-deployment** gate for the canonical single-VM
GPU training job. It runs before `terraform apply` and never launches training.

## What it catches

The harness fails before apply for repository or deployment drift including:

- more than one training Run Recipe, training `Dockerfile.gcp`, or container
  training entrypoint;
- GPU startup paths that reintroduce DVC commands or `dvc.lock` gates;
- malformed or unformatted Terraform;
- provider initialization or schema validation failures;
- plans that unexpectedly update, replace, or destroy infrastructure;
- plans that manage anything other than the single disposable training VM;
- invalid Compute Engine name length;
- unexpected machine, GPU, Local SSD, scheduling, network, or OAuth-scope shape;
- missing project, zone, machine type, GPU type, auto-mode VPC, or service account;
- unresolved Deep Learning VM image family;
- missing or mutable training image instead of an Artifact Registry digest;
- unreadable or malformed `dataset-artifact.json`;
- missing dataset image prefix or pinned annotation generation;
- insufficient observable CPU/GPU/external-IP/Local-SSD quota;
- inability to write durable run evidence.

Cloud capacity can still disappear between preflight and apply. Passing
preflight establishes that the reviewed deployment is internally coherent and
known prerequisites are present; it is not a GPU reservation.

## Dataset seam

The Dataset Artifact is versioned upstream. GPU preflight consumes, parses, and
hashes the published `dataset-artifact.json`; it does not generate a DVC lock or
re-version the dataset. The resulting manifest SHA-256 is written into
`deployment-manifest.json` and later compared with the manifest actually staged
by the VM.

## Run

From the repository root:

```bash
python terraform/preflight/preflight.py \
  --var-file /path/to/run.tfvars
```

Individual Terraform variables may also be supplied directly:

```bash
python terraform/preflight/preflight.py \
  --var 'run_id=run-20260926-a' \
  --var 'project_id=my-project' \
  --var 'service_account_email=trainer@my-project.iam.gserviceaccount.com' \
  --var 'training_image=us-east4-docker.pkg.dev/my-project/repo/trainer@sha256:<digest>' \
  --var 'dataset_artifact_prefix=datasets/coco/train2017/variant-a' \
  --var 'source_annotation_generation=1756000000000001' \
  --var 'artifact_prefix=gs://my-operations-bucket/runs/detection'
```

Use `--skip-write-probe` only when a read-only cloud preflight is explicitly
required. That reduces coverage because run-artifact writeability is not proven.

## Reports and checkpoints

Every invocation writes a timestamped directory under `reports/` unless
`--report-dir` is supplied. A passing run contains:

- `preflight-report.txt` — ordered human-readable checkpoint history;
- `preflight-report.json` — structured results with commands and timings;
- `deployment.tfplan` — exact saved Terraform plan inspected by preflight;
- `deployment-plan.json` — machine-readable plan used for contract checks;
- `deployment-manifest.json` — apply handoff containing the plan SHA-256,
  digest-pinned training image, Dataset Artifact URI and manifest SHA-256, and
  other reviewed deployment facts.

Major checkpoints are:

1. `LOCAL_TOOLING`
2. `REPOSITORY_CONTRACT`
3. `STATIC_TERRAFORM`
4. `TERRAFORM_PLAN`
5. `PLAN_CONTRACT`
6. `GCP_PREREQUISITES`
7. `ARTIFACT_WRITE_PROBE`
8. `DEPLOYMENT_MANIFEST`
9. `SUMMARY`

A `FAIL` is blocking. A `WARN` records reduced certainty only where Google Cloud
does not expose a dependable blocking signal. Do not downgrade a failed
contract to a warning merely to get an apply through.

## Apply discipline

Review the exact saved plan:

```bash
terraform -chdir=terraform/runs/detection show \
  terraform/preflight/reports/<timestamp>/deployment.tfplan
```

Then apply through the canonical launcher:

```bash
scripts/runs/detection.sh \
  --manifest terraform/preflight/reports/<timestamp>/deployment-manifest.json
```

The launcher hashes `deployment.tfplan` again and refuses to apply it if the
plan differs from what preflight approved. It then reports major apply/runtime
checkpoints and verifies that the Dataset Artifact manifest hash observed by
the VM matches the hash recorded during preflight.

Do not rerun `terraform plan` between review and apply. Do not call
`terraform apply` directly for this GPU workflow unless diagnosing the launcher
itself under explicit operator control.
