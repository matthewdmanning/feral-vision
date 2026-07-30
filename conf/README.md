# Configuration

## Purpose

`conf/` holds version-controlled parameter values for Feral Vision. It does not
define program flow or tooling boundaries.

## Selection

Choose a complete named Run Recipe: `runs/baseline` is the canonical local
recipe and `runs/smoke` is CPU-safe for validation. There is no root
`config.yaml` selection layer.

## Ownership

Python schemas own field contracts, YAML files own semantic variant values, and
Run Recipes own executable selection. The canonical program flow and tooling
ownership are defined in [the program flow](../docs/agents/program-flow.md).

The `deploy_schema` contract validates the root-level
[`deploy/cloudbuild.yaml`](../deploy/cloudbuild.yaml) parameter file. That file
is not a Run Recipe and does not define an operational workflow.
