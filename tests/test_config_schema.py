"""Structured-config schema tests: compose, validate, and CLI override."""

import pytest
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig, OmegaConf
from omegaconf.errors import ConfigAttributeError, ConfigKeyError

from feral_vision.config.store import register_configs


@pytest.fixture(autouse=True)
def _registered():
    register_configs()


@pytest.fixture(autouse=True)
def _clear_hydra():
    GlobalHydra.instance().clear()
    yield
    GlobalHydra.instance().clear()


def _compose(overrides=None):
    with initialize(version_base=None, config_path="../conf"):
        return compose(config_name="config", overrides=overrides or [])


def test_default_compose_is_mergeable_dictconfig():
    cfg = _compose()
    assert isinstance(cfg, DictConfig)
    merged = OmegaConf.merge(cfg, {"train": {"epochs": 5}})
    assert merged.train.epochs == 5


def test_cli_override_merges():
    cfg = _compose(["train.optim.lr=0.01", "inference.device=cuda"])
    assert cfg.train.optim.lr == 0.01
    assert cfg.inference.device == "cuda"


def test_unknown_key_rejected_by_struct_schema():
    with pytest.raises((ConfigKeyError, ConfigAttributeError, Exception)):
        _compose(["train.nope=1"])


def test_model_base_has_architecture_and_weights_fields():
    cfg = _compose()
    assert hasattr(cfg.model, "architecture")
    assert hasattr(cfg.model, "weights")
    assert hasattr(cfg.model, "model_outputs")


def test_model_base_architecture_defaults_to_local_net():
    """base.yaml no longer leaves architecture as MISSING sentinels (issue #16) —
    it defaults to the in-repo `local`/`net` architecture."""
    cfg = _compose()
    assert cfg.model.architecture.source == "local"
    assert cfg.model.architecture.id == "net"


def test_model_weights_defaults_null():
    cfg = _compose()
    assert cfg.model.weights is None


def test_model_variant_composes(tmp_path):
    with initialize(version_base=None, config_path="../conf"):
        cfg = compose(
            config_name="config",
            overrides=[
                "model=yolo11n_seg",
                "model.architecture.source=yolo_hub",
                "model.architecture.id=yolo11n-seg",
                "model.architecture.location=models/registry",
            ],
        )
    assert cfg.model.architecture.source == "yolo_hub"
    assert cfg.model.architecture.id == "yolo11n-seg"


def test_model_with_weights_block():
    from feral_vision.config.schema import ModelConfig, SourceConfig, WeightsConfig

    arch = SourceConfig(source="yolo_hub", id="yolo11n-seg", location="models/registry")
    weights = WeightsConfig(
        source="yolo_hub",
        id=["yolo11n-seg.pt"],
        location="models/checkpoints/yolo11n_seg",
    )
    cfg = OmegaConf.structured(
        ModelConfig(architecture=arch, weights=weights, model_outputs=["seg_instance"])
    )
    assert cfg.weights.source == "yolo_hub"
    assert "yolo11n-seg.pt" in cfg.weights.id


def test_model_outputs_list():
    with initialize(version_base=None, config_path="../conf"):
        cfg = compose(
            config_name="config",
            overrides=[
                "model=yolo11n_seg",
                "model.architecture.source=yolo_hub",
                "model.architecture.id=yolo11n-seg",
                "model.architecture.location=models/registry",
                "model.model_outputs=[seg_instance]",
            ],
        )
    assert "seg_instance" in cfg.model.model_outputs
