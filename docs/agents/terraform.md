# Terraform

Use this guide for Terraform modules, state, plans, and Cloud Resource
lifecycle. Use [Cloud Operations](cloudops.md) for cloud identity, image builds,
VM operations, and cloud training operations.
Terraform test placement is defined in the [Terraform test boundary](testing.md#terraform-test-boundary).

You have access to two distinct documentation tools for Terraform and Infrastructure as Code:

1. **Terraform MCP Server**: Live integration with the official Terraform Registry API and HCP Terraform.
2. **Context7**: Deep code and documentation retrieval indexed directly from GitHub repositories (`context7.com/<owner>/<repo>`).

Use these tools together according to the resolution matrix and execution workflow below.

---

## Tool Resolution Matrix

| Task / Need | Primary Tool | Secondary Tool |
| :--- | :--- | :--- |
| **Discovering module/provider names** | **Terraform MCP Server** (Registry Search) | — |
| **Checking exact version numbers** | **Terraform MCP Server** | — |
| **Checking required inputs/outputs & schema** | **Terraform MCP Server** | Context7 |
| **Finding working HCL code snippets** | **Context7** | Terraform MCP Server |
| **Understanding multi-file module architecture** | **Context7** | — |
| **Checking workspace state/variables** | **Terraform MCP Server** | — |

---

### Execution Protocol

When generating or editing Terraform code, execute actions in this specific order:

1. **Step 1: Schema & Version Verification (Terraform MCP)**
   * Query the Terraform MCP Server to identify the official module/provider source and the latest stable version.
   *[text](../_build) Fetch the schema to verify exact input variable names, data types, and required vs. optional fields.

2. **Step 2: Idiomatic Pattern Retrieval (Context7)**
   * Query Context7 (`context7.com/<owner>/<repo>`) for the corresponding repository to retrieve working code examples, sub-modules, and recommended setup patterns.
   * Use Context7 to understand real-world usage that goes beyond basic schema definitions (e.g., conditional flags, nested blocks, dependent resources).

3. **Step 3: Code Synthesis**
   * Combine the verified schema parameters from Step 1 with the idiomatic code structures from Step 2.
   * Ensure strict pinning of `source` and `version` blocks using the real-time data fetched from Step 1.

---

### 3. Constraints & Guardrails

* **Do not guess variable names**: If a module variable is unconfirmed, verify it via the MCP Server schema first.
* **Do not invent version numbers**: Always reference the exact version string returned by the Terraform MCP Server.
* **Prefer official Context7 repos**: Match the module source found in the MCP search directly to its corresponding GitHub repository in Context7.

## Banned resources

Subnetworks are banned. No Terraform file in this repository may create,
import, manage, or read a subnetwork, and no module or run variable may name
one. A VM attaches to its network and Compute Engine selects the regional
range; Cloud NAT uses
`source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES"`
and declares no subnetwork block. That provider field name and its enum are
the Google provider's schema, not a project-declared subnetwork.

This requires an auto-mode VPC. A custom-mode network cannot be addressed
without naming a subnetwork, so moving to one would need this rule revisited
rather than worked around.

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

* [`terraform/modules/`](../../terraform/modules/) contains reusable resource
  modules for Compute Engine and Cloud NAT. Existing network infrastructure is
  read through a data source, never imported or managed, and no module
  references a subnetwork.
* [`terraform/runs/`](../../terraform/runs/) contains run-scoped Terraform
  roots. `detection/` is the detection training root; it is parameterized by
  `run_id` and is not copied per run.
* [`terraform/tests/`](../../terraform/tests/) is the harness root for
  `*.tftest.hcl` contract tests. They use a mocked Google provider, so they
  need no credentials:

~~~bash
terraform -chdir=terraform/tests init
terraform -chdir=terraform/tests test
~~~

* Each run root's `versions.tf` declares its Terraform and provider version
  constraints, and its own backend `prefix`. Two roots must never share a
  state prefix; do not upgrade the constraints incidentally.

## State, inputs, and plans

Keep Terraform state in a protected operations location with fine-grained
access; it is not a Dataset Artifact location. Do not copy `.env.local` values
into Terraform variables, plans, state, logs, or documentation.

Validate formatting and configuration before planning. Review the saved plan
artifact before an approved apply. Before any destroy, create and review a
destroy plan that shows all affected resources and dependents; never use
`-auto-approve` for destroy.

## Provider plugin execution

Terraform `validate` must run in an environment that permits provider plugins
to create local Unix sockets. With Terraform `1.15.8` and the pinned Google
provider `6.50.0`, a restricted execution sandbox can produce:

~~~text
listen unix /tmp/plugin...: setsockopt: operation not permitted
~~~

This means the provider process started but the execution environment blocked
its local plugin handshake. It is not a Google Cloud authentication failure,
provider-schema failure, or invalid resource configuration. Run validation on a
normal host/CI runner or use the approved unsandboxed execution path:

~~~bash
terraform -chdir=terraform/runs/detection validate
terraform -chdir=terraform/runs/dvc_publication validate
~~~

Do not change provider versions or Terraform resource configuration to work
around this socket-permission error. Resolve the execution-environment
restriction first, then interpret any remaining Terraform diagnostics.
