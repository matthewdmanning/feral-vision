# Draft: Cloud Operations conceptual understanding

## Purpose

This draft captures the shared, high-level understanding reached during the
cloud-operations grilling session. It is not an implementation plan.

## Vocabulary

- An **Activity** groups responsibilities and functions that have a common
  environment or purpose.
- **Cloud Operations** is the Activity concerned with functions and operations
  performed in, or in support of, the cloud.
- A **Run Recipe** is YAML information. A Bash or Python script consumes it;
  the recipe does not execute work itself.
- A **Cloud Workflow** is a forked, directed, acyclic workflow. It is not a
  linear fixed sequence or a Run Recipe.
- **Orchestration** coordinates work with service providers. A Cloud Workflow
  can use multiple orchestrators, including hierarchical orchestrators.
- A **Cloud Service Provider** supplies Cloud Resources. The current provider
  is Google Cloud Services.
- **Terraform** is an orchestrator that obtains Cloud Resources from the Cloud
  Service Provider and manages their lifecycle. It is distinct from the
  provider.

## Workflow overview

A Cloud Workflow begins when a Bash or Python script consumes a Run Recipe.
The recipe states the desired work. Orchestration then coordinates the selected
branches with service providers.

The workflow has independent branches. Data and model/image preparation are
conditional: a particular run need not perform each branch. Terraform is the
required resource branch for every Cloud Workflow.

Cloud operations are idempotent. Local preparation is permitted when it
supports cloud work, but it does not establish cloud state. An explicit
cloud-operation capability checks that state before an existing input is
re-downloaded or recreated. An exact duplicate is suppressed only after a
successful prior run is known.

## Boundary for later clarification

The current repository code has not yet been reconciled with the intended
orchestrator hierarchy. In particular, the exact role and generated outputs of
each orchestrator require a separate, implementation-focused review.
