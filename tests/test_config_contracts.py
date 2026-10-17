"""Verify named Hydra recipes preserve executable configuration contracts."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from hydra.errors import ConfigCompositionException
from omegaconf import DictConfig, OmegaConf

from sightkit_learn.config.store import register_configs
from sightkit_learn.models.register_model import get_adapter

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CONF_ROOT = _REPOSITORY_ROOT / "feral-vision" / "conf"
_CANONICAL_RECIPE = _CONF_ROOT / "runs" / "detection.yaml"
_REQUIRED_CONCERNS = frozenset(
    {"data", "model", "train", "inference", "tracking", "augmentation"}
)


def _recipe_paths() -> tuple[Path, ...]:
    """Return every complete executable or test-only recipe path."""
    paths: list[Path] = []
    for directory in ("runs", "testing"):
        recipe_dir = _CONF_ROOT / directory
        if recipe_dir.exists():
            paths.extend(sorted(recipe_dir.glob("*.yaml")))
    return tuple(paths)


def _test_recipe_paths() -> tuple[Path, ...]:
    """Return recipes that must be safe to compose and run on CPU-only CI."""
    return tuple(path for path in _recipe_paths() if path.parent.name == "testing")


def _config_name(path: Path) -> str:
    """Convert a configuration file path into Hydra's extension-free name."""
    return path.relative_to(_CONF_ROOT).with_suffix("").as_posix()


def _compose_recipe(path: Path, overrides: list[str] | None = None) -> DictConfig:
    """Compose one complete recipe after registering the structured schemas."""
    with initialize(version_base=None, config_path="../feral-vision/conf"):
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
    resolved_config = OmegaConf.to_container(cfg, resolve=True, throw_on_missing=True)

    assert _REQUIRED_CONCERNS <= set(cfg)
    assert isinstance(resolved_config, dict)


@pytest.mark.parametrize("batch_size", [1, 3, 10])
@pytest.mark.parametrize("recipe_path", _recipe_paths(), ids=_config_name)
def test_recipe_applies_valid_cli_overrides(recipe_path: Path, batch_size: int) -> None:
    """Run Recipes accept valid structured CLI overrides for tunable values."""
    cfg = _compose_recipe(recipe_path, [f"train.batch_size={batch_size}"])

    assert cfg.train.batch_size == batch_size


@pytest.mark.parametrize("recipe_path", _test_recipe_paths(), ids=_config_name)
def test_test_recipe_is_cpu_safe(recipe_path: Path) -> None:
    """Validation recipes never require a GPU or background data workers."""
    cfg = _compose_recipe(recipe_path)

    assert cfg.train.device == "cpu"
    assert cfg.train.num_workers == 0


def test_recipe_rejects_unknown_structured_override() -> None:
    """The canonical Run Recipe rejects fields outside registered schemas."""
    with pytest.raises(
        ConfigCompositionException, match="Could not override 'train.nope'"
    ):
        _compose_recipe(_CANONICAL_RECIPE, ["train.nope=1"])


@pytest.mark.parametrize(
    "task",
    [
        "classification",
        "detection",
        "semantic_segmentation",
        "instance_segmentation",
        "panoptic_segmentation",
        "pose",
    ],
)
def test_common_task_and_publication_options_are_hydra_overrides(task):
    """Existing recipes select common tasks and publication behavior without Python edits."""
    cfg = _compose_recipe(
        _CANONICAL_RECIPE,
        [
            f"train.task={task}",
            "train.loss_mode=auto",
            "train.monitor=train_loss",
            "train.mode=min",
            "tracking.serialization_format=pickle",
            "tracking.model_name=selected-model",
        ],
    )

    assert cfg.train.task == task
    assert cfg.train.loss_mode == "auto"
    assert cfg.tracking.serialization_format == "pickle"
    assert cfg.tracking.model_name == "selected-model"


def test_native_inference_options_are_hydra_overrides():
    """The existing schema configures an MLflow model and native calling options."""
    cfg = _compose_recipe(
        _CANONICAL_RECIPE,
        [
            "inference.model_uri=models:/vision@champion",
            "inference.call_mode=kwargs",
            "+inference.forward_kwargs={return_dict:true}",
            "+inference.load_kwargs={dst_path:/tmp/inference-cache}",
        ],
    )

    assert cfg.inference.model_uri == "models:/vision@champion"
    assert cfg.inference.call_mode == "kwargs"
    assert cfg.inference.forward_kwargs.return_dict is True
    assert cfg.inference.load_kwargs.dst_path == "/tmp/inference-cache"


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
    cfg = _compose_recipe(_CANONICAL_RECIPE, [f"model={model_path.stem}"])
    architecture = cfg.model.architecture

    assert architecture.source
    assert architecture.id
    assert architecture.location
    assert "model_outputs" not in cfg.model
    assert _resolve_dotted_name(architecture.location) is not None
    if architecture.source != "local":
        assert get_adapter(architecture.source)
