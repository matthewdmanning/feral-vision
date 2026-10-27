# Terraform

Use this guide for Terraform state, plans, tests, and Cloud Resource lifecycle.
Use [Cloud Operations](cloudops.md) for image builds and GPU runtime behavior.

## Toolchain

Use Terraform 1.16 or later within 1.x and Google provider 8.x. The provider
version and checksums are locked independently in all three roots. Initialize
with `-backend=false` for local validation without accessing GCS state.

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
| `feral-vision/terraform/preflight/` | Deployment preflight |

Commit all three `.terraform.lock.hcl` files. A `terraform init` on another
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

Production and starter-template suites each contain 20 mocked plan scenarios.
They cover the fixed VM shape, resolved boot-image wiring, URI resolution,
invalid inputs, lifetime boundaries, custom identity/tags, and rendered startup
assignments. Bucket tests check caller-selected identity/location, uniform IAM,
public-access prevention, Object Retention Lock support, disabled versioning,
STANDARD storage, and seven-day soft delete. Mock defaults do not supply the
policy values being asserted.

Run both suites after changing shared Terraform behavior; the template suite is
under `src/templates/terraform/tests/`. Neither suite proves provider defaults,
IAM, backend access, startup execution, or live GCP prerequisites. The bucket's
`prevent_destroy` lifecycle rule is not exercised by these plan-only tests.

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
