# Terraform

Use this guide for Terraform state, plans, tests, and Cloud Resource lifecycle.
Use [Cloud Operations](cloudops.md) for image builds and GPU runtime behavior.

## Never in CI

Terraform is deployment tooling. It is not source code and not part of the
project test suite. No Terraform command (`init`, `validate`, `plan`, `test`,
`apply`, or `feral-vision/terraform/preflight/preflight.py`) may run in a GitHub workflow, a
git hook, or `tools/validate_ci.sh`. Run them by hand, on the operator's
machine, only.

## Documentation sources

Verify provider/resource behavior against the current Google provider schema and
Google Cloud documentation before changing Terraform. Use Context7 for provider
implementation/examples when useful. Do not guess resource arguments or
silently change provider/Terraform versions to work around an unrelated error.

## Banned resources

Subnetworks and Cloud NAT are banned. No Terraform file in this repository may
create, import, manage, or read a subnetwork, Cloud Router, or Cloud NAT, and no
variable may name one.

A training VM attaches to an existing auto-mode VPC and receives an ephemeral
external address through an empty `access_config` block. This means:

- the selected VPC must be auto-mode because this root intentionally does not
  name a subnetwork. The `google_compute_network` data source does not expose
  the VPC mode, so Terraform cannot check it. `preflight.py` checks
  `autoCreateSubnetworks` against the live network before every apply;
- existing firewall policy must be reviewed for an externally addressed VM;
- Terraform must not work around a network failure by introducing a router,
  NAT, firewall, or subnetwork into this training root.

## Canonical GPU root

`feral-vision/terraform/runs/detection/` is the only GPU training Terraform root. It manages
one disposable training VM and is reused only after the previous instance has
been removed. Do not copy this root per run or create a sibling GPU root.

The machine/GPU/SSD shape and training recipe are intentionally fixed. Add a
variable only when the deployment genuinely needs to vary between runs.
Terraform must not manage shared IAM, firewall, registry, bucket, or network
resources from this root.

## File map

Follow the HashiCorp Terraform style guide for layout and naming.

| Path | Contents |
| --- | --- |
| `feral-vision/terraform/runs/detection/terraform.tf` | Terraform version, provider requirements, and `gcs` backend |
| `feral-vision/terraform/runs/detection/providers.tf` | Provider configuration |
| `feral-vision/terraform/runs/detection/locals.tf` | Local values, including the fixed machine and GPU shape |
| `feral-vision/terraform/runs/detection/main.tf` | Data sources and the one `google_compute_instance` |
| `feral-vision/terraform/runs/detection/variables.tf` | Input variables, in alphabetical order |
| `feral-vision/terraform/runs/detection/outputs.tf` | Outputs, in alphabetical order |
| `feral-vision/terraform/runs/detection/templates/` | VM startup script template |
| `feral-vision/terraform/runs/detection/.terraform.lock.hcl` | Provider lock; commit it |
| `feral-vision/terraform/buckets/dataset/` | Dataset-only bucket root: versioning off, soft delete, Object Retention Lock, own `gcs` backend prefix |
| `feral-vision/terraform/tests/` | Mocked-provider tests (see below) |
| `feral-vision/terraform/preflight/` | Deployment gate (see below) |

Commit both `.terraform.lock.hcl` files. A `terraform init` on another
operating system can add platform hashes to them; review and commit that change
on purpose, not as a side effect.

## Mocked-provider tests

`feral-vision/terraform/tests/` contains mocked-provider tests. Name plan-mode test
files `*_unit_test.tftest.hcl`. Reserve `*_integration_test.tftest.hcl` for
apply-mode tests, which this repository does not have.

~~~bash
terraform -chdir=feral-vision/terraform/tests init
TF_VAR_test_gcs_uri_prefix="${GCS_URI_PREFIX:?Set GCS_URI_PREFIX first}" terraform -chdir=feral-vision/terraform/tests test
~~~

Run these tests by hand before a Terraform change. Never run them in CI, a git
hook, or `tools/validate_ci.sh`.

The tests cover the fixed VM shape, URI resolution, and negative tests for the
main variable validations. Some validations, such as the mount-directory
prefixes, have no negative test yet. Those tests are necessary but not sufficient for deployment
because they do not prove live GCP prerequisites.

## Required GPU deployment gate

Before every GPU apply, run:

~~~bash
python feral-vision/terraform/preflight/preflight.py --var-file /path/to/run.tfvars
~~~

The preflight must pass before apply. It checks:

- the repository still has one canonical training recipe/image/entrypoint;
- GPU runtime has not reintroduced DVC commands or a `dvc.lock` gate;
- Terraform formatting, initialization, and validation;
- a saved plan contains only the disposable training VM and no unexpected
  update/replacement/destroy action;
- the fixed machine, T4, NVMe Local SSD, on-demand scheduling, network, and
  service-account settings;
- live project/zone/machine/GPU/network/service-account/image prerequisites;
- the published `dataset-artifact.json`, its SHA-256, dataset image prefix, and
  generation-pinned annotations object;
- observable quota and artifact-output writeability.

A passing run emits `deployment-manifest.json`. That manifest pins the exact
saved plan SHA-256, training-image digest, Dataset Artifact URI, and Dataset
Artifact manifest SHA-256.

Review the saved plan, then apply only through:

~~~bash
feral-vision/scripts/runs/detection.sh \
  --manifest feral-vision/terraform/preflight/reports/<timestamp>/deployment-manifest.json
~~~

The launcher rejects a saved plan whose bytes changed after preflight. Do not
regenerate a plan between review and apply and do not use `-auto-approve` for
this workflow.

Keep the generated reports and manifest when diagnosing a failed deployment.
They record where provisioning stopped. Compare them across retries instead of
changing Terraform based only on the final error. See the
[preflight guide](../../feral-vision/terraform/preflight/README.md) for the report files.

## Dataset boundary

Terraform selects an already-published Dataset Artifact; it does not create or
version training data. GPU startup requires the published
`dataset-artifact.json` and generation-pinned annotation object. DVC-related
dataset publication remains upstream and must not be recreated on the training
VM.

## State and secrets

Keep Terraform state in the protected operations backend. State is not a
Dataset Artifact location. Do not copy `.env.local` values into variables,
plans, state, logs, or documentation.

Each Terraform root owns a distinct backend prefix. Never make two roots share
a state prefix.

## Destroy

Container exit does not remove the VM. Removal is a Terraform lifecycle action.
Always generate and review a destroy plan before applying it:

~~~bash
terraform -chdir=feral-vision/terraform/runs/detection plan -destroy -out=destroy.tfplan
terraform -chdir=feral-vision/terraform/runs/detection show destroy.tfplan
terraform -chdir=feral-vision/terraform/runs/detection apply destroy.tfplan
~~~

Never use `-auto-approve` for destroy.

## Provider plugin execution

Terraform `validate` must run in an environment that permits provider plugins
to create local Unix sockets. A restricted sandbox can fail the provider
handshake with an error such as:

~~~text
listen unix /tmp/plugin...: setsockopt: operation not permitted
~~~

That is an execution-environment restriction, not evidence of a Google Cloud
authentication or resource-schema problem. Re-run validation on a normal
host/CI runner before changing provider versions or Terraform configuration.
