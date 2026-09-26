# Detection training run

One self-contained Terraform root for a **single disposable GPU training VM**.
It consumes a Dataset Artifact already published to the dataset-only Cloud
Storage bucket. The root is reused only after the previous VM is removed; one
Terraform state never manages concurrent trainers.

## Fixed deployment shape

This root creates exactly one `n1-standard-4` VM with one NVIDIA T4, one NVMe
Local SSD, a 100 GB `pd-ssd` boot disk, and Flex-start scheduling. Shared IAM,
firewall, router, NAT, subnetwork, registry, bucket, and network resources are
not managed here.

The trainer reads an existing auto-mode VPC and receives an ephemeral external
IPv4 address for Artifact Registry and Cloud Storage egress. Existing firewall
policy may select the VM through `instance_tags`.

## Required variables

| Variable | Meaning |
| --- | --- |
| `run_id` | Scopes VM/evidence names; 3–40 characters |
| `project_id` | Project that owns the VM |
| `service_account_email` | Existing reviewed VM identity |
| `training_image` | Digest-pinned canonical training image |
| `dataset_artifact_prefix` | `datasets/...` prefix holding payload + `dataset-artifact.json` |
| `source_annotation_generation` | Retained generation of `payload/annotations/instances.json` |
| `artifact_prefix` | Writable non-dataset `gs://` evidence prefix |

Machine/GPU/SSD shape and the training recipe are deliberately not variables.
The only supported recipe is `conf/runs/detection.yaml`.

## Data-versioning / training seam

Dataset versioning happens upstream. The GPU run does not initialize or run DVC.
The published Dataset Artifact is the input boundary:

1. preflight reads and parses `dataset-artifact.json` and records its SHA-256;
2. the VM stages images, the generation-pinned annotations object, and the exact
   published `dataset-artifact.json` onto Local SSD;
3. startup parses the staged manifest and hashes it before touching the GPU;
4. the container entrypoint verifies that hash again before training;
5. MLflow lineage and `training-evidence.json` record the manifest SHA-256;
6. the exact manifest is copied to the run evidence prefix.

A `.dvc` tracker or `dvc.lock` is not created, required, or uploaded by this GPU
workflow. Upstream dataset publication owns those concerns where applicable.

## Build the training image

There is one supported training image path:

```bash
scripts/cloud/build_training_image.sh \
  --project <project> \
  --region <region> \
  --repository <artifact-registry-repository> \
  --image feral-vision-training \
  --tag <immutable-build-tag>
```

The script builds `deploy/Dockerfile.gcp` through
`deploy/cloudbuild.training-image.yaml`, runs image-contract checks before the
push, then prints the digest-pinned Artifact Registry reference required by
Terraform.

## Preflight and apply

Do not use `terraform apply` to discover configuration errors. Run preflight
with the exact deployment inputs:

```bash
python terraform/preflight/preflight.py --var-file /path/to/run.tfvars
```

Preflight verifies the canonical repository shape, Terraform syntax/schema and
saved plan, single-VM plan contract, GCP prerequisites, Dataset Artifact
manifest, pinned annotations generation, relevant quotas, and run-artifact
writeability. See [`../../preflight/README.md`](../../preflight/README.md).

Review the generated `deployment.tfplan`, then apply only through the generated
manifest:

```bash
scripts/runs/detection.sh \
  --manifest terraform/preflight/reports/<timestamp>/deployment-manifest.json
```

The launcher refuses a plan whose SHA-256 changed after preflight. It retains
serial output, polls terminal training evidence, and checks that the Dataset
Artifact manifest observed by the VM matches the preflight hash.

VM `RUNNING` status is not training success. `training-evidence.json` is the
terminal run record.

## Runtime checkpoints

The startup script logs major stages to the serial console:

- `mount_local_ssd`
- `pull_training_image`
- `verify_dataset_artifact`
- `stage_dataset_payload`
- `verify_staged_dataset`
- `verify_gpu`
- `train`
- `done`

On failure, terminal evidence records `failed_stage` before being uploaded when
possible.

## Destroy

Container exit does not remove the VM. Removal is a Terraform lifecycle action
and requires a separately reviewed destroy plan:

```bash
terraform -chdir=terraform/runs/detection plan -destroy -out=destroy.tfplan
terraform -chdir=terraform/runs/detection show destroy.tfplan
terraform -chdir=terraform/runs/detection apply destroy.tfplan
```

## Terraform contract tests

Contract tests live in `terraform/tests/` and use a mocked provider:

```bash
terraform -chdir=terraform/tests init
terraform -chdir=terraform/tests test
```
