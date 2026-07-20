# Feral Vision

Feral Vision is a research repository for feral-cat instance segmentation from
mobile-captured images. It supports downstream tracking, population monitoring,
and trap-neuter-return work.

## Start here

- [Program flow and tooling ownership](ARCHITECTURE.md)
- [Product scope and delivery constraints](docs/planning/product-scope.md)
- [User and API documentation](docs/index.rst)

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
