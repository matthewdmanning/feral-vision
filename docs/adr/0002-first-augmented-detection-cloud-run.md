# First augmented detection cloud run

## Status

**Superseded.** This ADR records the August 2026 run-specific deployment design
and is retained only as historical context. Do not use its old script names,
run-specific image layout, DVC-on-training assumptions, or Run Recipe names as
operational instructions.

The current GPU training contract is defined by:

- [`AGENTS.md`](../../AGENTS.md)
- [Cloud operations](../agents/cloudops.md)
- [Program flow](../agents/program-flow.md)
- [Training guide](../guide/training.rst)
- [`terraform/runs/detection/README.md`](../../terraform/runs/detection/README.md)

## Historical decision

The original first augmented-detection experiment separated upstream Dataset
Variant materialization from a disposable GPU VM. Its important durable
boundary remains valid: dataset preparation/versioning happens upstream, and
training consumes a published immutable Dataset Artifact rather than mutating
its source data.

The implementation details from this ADR have since been replaced. In
particular:

- `dataset-artifact.json` is now the explicit data-versioning/training seam;
- the GPU runtime does not initialize or reproduce DVC state;
- there is one complete training recipe, `conf/runs/detection.yaml`;
- there is one GPU training image, `deploy/Dockerfile.gcp`;
- image build, deployment preflight, Terraform apply, and terminal evidence use
  the canonical paths documented in `AGENTS.md`;
- the run-specific preparation/deployment wrappers described by the original
  ADR were removed because they had diverged from the supported Terraform and
  image contracts.

Upstream Dataset Artifact publication may still use DVC metadata. That
publication workflow is intentionally outside the GPU runtime contract and is
not redefined by this superseding note.
