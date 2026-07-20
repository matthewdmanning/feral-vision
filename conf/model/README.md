# Model configuration

Model configuration selects a reproducible model definition: its architecture
source, identifier, location, and optional starting weights. The model source
adapter owns source-specific behavior and inspected output metadata; a YAML
variant must not duplicate that metadata.

Choose a semantic model variant. The program-flow and model-acquisition
boundary are defined in [ARCHITECTURE.md](../../ARCHITECTURE.md).
