"""Configuration recipes and their documentation must preserve executable contracts."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig, OmegaConf

from feral_vision.config.store import register_configs
from feral_vision.models.register_model import get_adapter


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CONF_ROOT = _REPOSITORY_ROOT / "conf"
_REQUIRED_CONCERNS = frozenset(
    {"data", "model", "train", "inference", "tracking", "augmentation"}
)
_README_CONCERNS = (
    Path("."),
    Path("augmentation"),
    Path("data"),
    Path("inference"),
    Path("model"),
    Path("runs"),
    Path("tracking"),
    Path("train"),
    Path("train/loss_fn"),
    Path("train/optim"),
    Path("train/scheduler"),
)
_REQUIRED_README_HEADINGS = ("## Purpose", "## Selection", "## Ownership")


def _recipe_paths() -> tuple[Path, ...]:
    """Return every executable or test-only recipe path in the configuration tree."""
    paths: list[Path] = []
    for directory in ("runs", "testing"):
        recipe_dir = _CONF_ROOT / directory
        if recipe_dir.exists():
            paths.extend(sorted(recipe_dir.glob("*.yaml")))
    return tuple(paths)


def _test_recipe_paths() -> tuple[Path, ...]:
    """Return recipes that must be safe to compose and run on CPU-only CI."""
    return tuple(
        path
        for path in _recipe_paths()
        if path.parent.name == "testing" or path.stem == "smoke"
    )


def _config_name(path: Path) -> str:
    """Convert a configuration file path into Hydra's extension-free name."""
    return path.relative_to(_CONF_ROOT).with_suffix("").as_posix()


def _compose_recipe(path: Path, overrides: list[str] | None = None) -> DictConfig:
    """Compose one complete recipe after registering the structured schemas."""
    with initialize(version_base=None, config_path="../conf"):
        return compose(config_name=_config_name(path), overrides=overrides or [])


def _resolve_dotted_name(dotted_name: str) -> object:
    """Resolve one module-qualified object without instantiating it."""
    module_name, separator, attribute_name = dotted_name.rpartition(".")
    assert separator, f"location must be a dotted import path: {dotted_name!r}"
    return getattr(import_module(module_name), attribute_name)


@pytest.fixture(autouse=True)
def _registered_and_isolated_hydra() -> None:
    """Register schemas and clear Hydra state around each composition test."""
    register_configs()
    GlobalHydra.instance().clear()
    yield
    GlobalHydra.instance().clear()


# ---------------------------------------------------------------------------
# Run Recipes — complete and reproducible configuration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("recipe_path", _recipe_paths(), ids=_config_name)
def test_recipe_composes_without_missing_values(recipe_path: Path) -> None:
    """Every supported recipe resolves all required configuration concerns."""
    cfg = _compose_recipe(recipe_path)

    assert _REQUIRED_CONCERNS <= set(cfg)
    assert OmegaConf.to_container(cfg, resolve=True, throw_on_missing=True)


@pytest.mark.parametrize("recipe_path", _test_recipe_paths(), ids=_config_name)
def test_test_recipe_is_cpu_safe(recipe_path: Path) -> None:
    """Validation recipes never require a GPU or background data workers."""
    cfg = _compose_recipe(recipe_path)

    assert cfg.train.device == "cpu"
    assert cfg.train.num_workers == 0


def test_legacy_configuration_paths_are_not_selectable() -> None:
    """Retired root/default/base/experiment configuration paths stay absent."""
    retired_files = [
        path.relative_to(_CONF_ROOT)
        for path in _CONF_ROOT.rglob("*.yaml")
        if path.stem in {"base", "config", "default"}
    ]

    assert not retired_files
    assert not (_CONF_ROOT / "experiment").exists()


# ---------------------------------------------------------------------------
# Model variants — source, location, and metadata ownership
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_path",
    sorted((_CONF_ROOT / "model").glob("*.yaml")),
    ids=lambda path: path.stem,
)
def test_model_variant_has_a_resolvable_source_location_and_schema(
    model_path: Path,
) -> None:
    """Each selectable model declares a source, identifier, and importable location."""
    cfg = _compose_recipe(
        _CONF_ROOT / "runs" / "baseline.yaml", [f"model={model_path.stem}"]
    )
    architecture = cfg.model.architecture

    assert architecture.source
    assert architecture.id
    assert architecture.location
    assert "model_outputs" not in cfg.model
    assert _resolve_dotted_name(architecture.location)
    if architecture.source != "local":
        assert get_adapter(architecture.source)


# ---------------------------------------------------------------------------
# Configuration documentation — topology and canonical ownership
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("concern", _README_CONCERNS, ids=lambda path: path.as_posix())
def test_configuration_concern_readme_has_the_canonical_structure(
    concern: Path,
) -> None:
    """Each configuration concern explains purpose, selection, and ownership once."""
    readme_path = _CONF_ROOT / concern / "README.md"
    contents = readme_path.read_text(encoding="utf-8")

    for heading in _REQUIRED_README_HEADINGS:
        assert heading in contents
    assert "docs/architecture/program-flow.md" in contents
