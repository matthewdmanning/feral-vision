# Feral Vision

Feral Vision is a research repository for feral-cat instance segmentation from
mobile-captured images. It supports downstream tracking, population monitoring,
and trap-neuter-return work.

## Start here

- [Program flow and tooling ownership](docs/agents/program-flow.md)
- [User and API documentation](docs/index.rst)

## Layout

- `src/sightkit_learn/`: reusable library, distributed as `sightkit-learn`.
- `src/templates/`: packaged starter workflow assets.
- `feral-vision/`: project recipes, scripts, deployment files, Terraform, data, and models; excluded from the release.
- `tools/`, `tests/`, and `docs/`: development tooling and documentation.

The module authority is [Modules](docs/domain/modules.md). Imports previously
using `feral_vision` now use `sightkit_learn`. Run project workflow commands from
`feral-vision/`; image builds retain the repository root as their build context.
Existing MLflow metadata keys remain unchanged for persisted-run compatibility.

## Development

```bash
uv sync
uv run python -m pytest
```

The project is not published as a package. See the repository documentation for
dataset preparation, local development, and Docker/GCE training guidance.

## Contributing

Follow the repository instructions in `AGENTS.md` or `CLAUDE.md`. Keep durable
knowledge in its canonical document and link to it from entrypoints instead of
copying it.
