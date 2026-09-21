# Detection training run

One Terraform root that trains on a Dataset Artifact already published to the
dataset-only Cloud Storage bucket. It is parameterized by `run_id`; it is not
copied per run.

## What it owns

| Resource | Ownership |
| --- | --- |
| Disposable GPU training VM | Created here, named `feral-vision-detection-<run_id>` |
| Cloud Router and Cloud NAT | Created here when `create_cloud_nat` is `true`, named from `run_id` |
| Dataset bucket | Read only, through `data.google_storage_bucket` |
| Subnetwork | Read only, through `data.google_compute_subnetwork` |
| IAM | Never created or modified |

Nothing shared is imported or managed, so a destroy plan for a run can only
reach that run's own resources.

## Required variables

| Variable | Meaning |
| --- | --- |
| `run_id` | Scopes every created resource name and the evidence prefix |
| `project_id` | Project that owns the VM and its egress path |
| `service_account_email` | Existing, reviewed VM identity |
| `training_image` | Digest-pinned image; a mutable tag is rejected |
| `dataset_artifact_prefix` | `datasets/...` prefix holding the payload and manifest |
| `source_annotation_generation` | Retained generation of `payload/annotations/instances.json` |
| `artifact_prefix` | Writable `gs://` prefix for evidence; must not be the dataset bucket |

Everything else has a default. See `variables.tf` for the validations that
enforce these contracts at plan time.

## Flow

The VM stages `<dataset_artifact_prefix>/payload` onto its local SSD, pins the
annotation to `source_annotation_generation`, versions the staged Dataset with
DVC on the VM, verifies the resulting lock, trains, and exports MLflow outputs,
the DVC lock, and `training-evidence.json` to `<artifact_prefix>/<run_id>`.
Evidence is exported on failure as well as success.

Container exit does not remove the VM. Removing it is a Terraform lifecycle
action that requires a reviewed destroy plan:

~~~bash
terraform -chdir=terraform/runs/detection plan -destroy -out=destroy.tfplan
terraform -chdir=terraform/runs/detection show destroy.tfplan
terraform -chdir=terraform/runs/detection apply destroy.tfplan
~~~

## Tests

Contract tests live in [`terraform/tests/`](../../tests/) and run against a
mocked provider, so they need no credentials:

~~~bash
terraform -chdir=terraform/tests init
terraform -chdir=terraform/tests test
~~~
