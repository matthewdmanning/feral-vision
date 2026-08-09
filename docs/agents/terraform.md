# Terraform

Use this guide for Terraform modules, state, plans, and Cloud Resource
lifecycle. Use [Cloud Operations](cloudops.md) for cloud identity, image builds,
VM operations, and cloud training operations.

## Ownership

Terraform can orchestrate any operation performed in the cloud; it is not
limited to GPU model training. It owns the configuration and lifecycle of Cloud
Resources, including storage, registries, compute, network, identity, and
access policy. A Terraform program declares or references the resources it
creates or requisitions.

Operational scripts direct the selected operation and use provisioned services
without recreating or redefining them. GPU model training requires
Terraform-provisioned Cloud Resources, but does not define Terraform's
orchestration behavior. For VM-backed operations, container exit does not
remove the VM; VM removal is a Terraform lifecycle action.

## Files

- [`terraform/main.tf`](../../terraform/main.tf),
  [`terraform/variables.tf`](../../terraform/variables.tf), and
  [`terraform/outputs.tf`](../../terraform/outputs.tf) define shared Cloud
  Resources and their inputs and outputs.
- [`terraform/runs/`](../../terraform/runs/) contains run-scoped Terraform
  modules, including detection training infrastructure.
- [`terraform/tests/`](../../terraform/tests/) contains Terraform tests.
- [`terraform/versions.tf`](../../terraform/versions.tf) declares the Terraform
  and provider version constraints; do not upgrade them incidentally.

## State, inputs, and plans

Keep Terraform state in a protected operations location with fine-grained
access; it is not a Dataset Artifact location. Do not copy `.env.local` values
into Terraform variables, plans, state, logs, or documentation.

Validate formatting and configuration before planning. Review the saved plan
artifact before an approved apply. Before any destroy, create and review a
destroy plan that shows all affected resources and dependents; never use
`-auto-approve` for destroy.
