# Data configuration

Data configuration selects the dataset source and the parameters needed to
resolve it to the repository's canonical dataset layout. It is a Hydra concern;
DVC owns the underlying data artifacts. See [ARCHITECTURE.md](../../ARCHITECTURE.md)
for the data-flow and tooling boundary.

Choose a semantic dataset variant for a reproducible run. Dataset acquisition,
derivation, and version identity are described by the project vocabulary in
[CONTEXT.md](../../CONTEXT.md).
