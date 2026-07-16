"""Validate every conf/model/*.yaml against the model-endpoint contract (issue #16).

Composes each model config variant via Hydra and asserts:
  - architecture.source is set (not the Hydra MISSING "???" sentinel).
  - architecture.id is set.
  - if source == "local", architecture.id resolves in model_registry.json (i.e.
    the in-repo class it names has actually been registered).

Not a pytest test: yaml correctness is a config concern, not source-code
behavior, so it's checked here rather than in tests/.

Usage:
    uv run python scripts/validate_model_yaml.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

_CONF_MODEL_DIR = Path(__file__).parent.parent / "conf" / "model"


def _model_variants() -> list[str]:
    """Return the model config group variant names (yaml filenames minus extension)."""
    return sorted(f.stem for f in _CONF_MODEL_DIR.glob("*.yaml"))


def validate_variant(name: str) -> None:
    """Compose and validate a single conf/model/<name>.yaml.

    Parameters
    ----------
    name : str
        Model config group variant name (matches the yaml filename stem).

    Raises
    ------
    AssertionError
        If the composed config doesn't satisfy the model-endpoint contract.
    """
    from hydra import compose, initialize
    from hydra.core.global_hydra import GlobalHydra
    from omegaconf.errors import MissingMandatoryValue

    from feral_segmentor.config.store import register_configs
    from feral_segmentor.models import register_model  # noqa: F401 -- triggers @register

    register_configs()
    GlobalHydra.instance().clear()
    try:
        with initialize(version_base=None, config_path="../conf"):
            cfg = compose(config_name="config", overrides=[f"model={name}"])
    finally:
        GlobalHydra.instance().clear()

    try:
        source = cfg.model.architecture.source
        arch_id = cfg.model.architecture.id
    except MissingMandatoryValue as exc:
        raise AssertionError(
            f"conf/model/{name}.yaml: architecture.source/id left as MISSING (???)"
        ) from exc

    assert source, f"conf/model/{name}.yaml: architecture.source is empty"
    assert arch_id, f"conf/model/{name}.yaml: architecture.id is empty"

    if source == "local":
        register_model.registered_config(arch_id)  # raises KeyError if unregistered


def main() -> None:
    """Validate every conf/model/*.yaml variant, printing PASS/FAIL per file."""
    failures: list[str] = []
    for name in _model_variants():
        try:
            validate_variant(name)
        except (AssertionError, KeyError) as exc:
            failures.append(f"{name}: {exc}")
            print(f"FAIL  conf/model/{name}.yaml — {exc}")
        else:
            print(f"OK    conf/model/{name}.yaml")

    if failures:
        raise SystemExit(f"{len(failures)} model config(s) failed validation")


if __name__ == "__main__":
    main()
