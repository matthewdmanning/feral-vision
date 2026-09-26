# Terraform

Use this guide for Terraform state, plans, tests, and Cloud Resource lifecycle.
Use [Cloud Operations](cloudops.md) for image builds and GPU runtime behavior.

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
  name a subnetwork;
- existing firewall policy must be reviewed for an externally addressed VM;
- Terraform must not work around a network failure by introducing a router,
  NAT, firewall, or subnetwork into this training root.

## Canonical GPU root

`terraform/runs/detection/` is the only GPU training Terraform root. It manages
one disposable training VM and is reused only after the previous instance has
been removed. Do not copy this root per run or create a sibling GPU root.

The machine/GPU/SSD shape and training recipe are intentionally fixed. Add a
variable only when the deployment genuinely needs to vary between runs.
Terraform must not manage shared IAM, firewall, registry, bucket, or network
resources from this root.

`terraform/tests/` contains mocked-provider contract tests:

~~~bash
terraform -chdir=terraform/tests init
terraform -chdir=terraform/tests test
~~~

Those tests are necessary but not sufficient for deployment because they do not
prove live GCP prerequisites.

## Required GPU deployment gate

Before every GPU apply, run:

~~~bash
python terraform/preflight/preflight.py --var-file /path/to/run.tfvars
~~~

The preflight must pass before apply. It checks:

- the repository still has one canonical training recipe/image/entrypoint;
- GPU runtime has not reintroduced DVC commands or a `dvc.lock` gate;
- Terraform formatting, initialization, and validation;
- a saved plan contains only the disposable training VM and no unexpected
  update/replacement/destroy action;
- the fixed machine, T4, NVMe Local SSD, Flex-start, network, and service-account
  contract;
- live project/zone/machine/GPU/network/service-account/image prerequisites;
- the published `dataset-artifact.json`, its SHA-256, dataset image prefix, and
  generation-pinned annotations object;
- observable quota and artifact-output writeability.

A passing run emits `deployment-manifest.json`. That manifest pins the exact
saved plan SHA-256, training-image digest, Dataset Artifact URI, and Dataset
Artifact manifest SHA-256.

Review the saved plan, then apply only through:

~~~bash
scripts/runs/detection.sh \
  --manifest terraform/preflight/reports/<timestamp>/deployment-manifest.json
~~~

The launcher rejects a saved plan whose bytes changed after preflight. Do not
regenerate a plan between review and apply and do not use `-auto-approve` for
this workflow.

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
terraform -chdir=terraform/runs/detection plan -destroy -out=destroy.tfplan
terraform -chdir=terraform/runs/detection show destroy.tfplan
terraform -chdir=terraform/runs/detection apply destroy.tfplan
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
