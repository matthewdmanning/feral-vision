# Configuration

`conf/` holds version-controlled parameters for Feral Vision. Program flow and
tool ownership are defined in [ARCHITECTURE.md](../ARCHITECTURE.md), not here.

Each configuration concern owns a co-located README that explains its purpose,
the choice it represents, and its owner. Typed field contracts belong in Python
schemas; YAML contains variant values; executable selections belong in named Run
Recipes. Do not duplicate those sources as README field tables or variant
inventories.

Run `runs/baseline` for the canonical local recipe or `runs/smoke` for a
CPU-safe configuration check. There is no root `config.yaml` selection layer.
