"""Foundation tests: structured-config schemas compose, validate, and stay mergeable."""

import pytest
from hydra import compose, initialize
from omegaconf import DictConfig, OmegaConf
from omegaconf.errors import ConfigAttributeError, ConfigKeyError

from feral_segmentor.config.store import register_configs


@pytest.fixture(autouse=True)
def _registered():
    register_configs()


def _compose(overrides=None):
    # config_path is relative to this test file (tests/ -> ../conf).
    with initialize(version_base=None, config_path="../conf"):
        return compose(config_name="config", overrides=overrides or [])


def test_default_compose_is_mergeable_dictconfig():
    cfg = _compose()
    assert isinstance(cfg, DictConfig)
    # Mergeable: a second config merges in cleanly.
    merged = OmegaConf.merge(cfg, {"train": {"epochs": 5}})
    assert merged.train.epochs == 5


def test_cli_override_merges():
    cfg = _compose(["train.optim.lr=0.01", "inference.device=cuda"])
    assert cfg.train.optim.lr == 0.01
    assert cfg.inference.device == "cuda"


def test_unknown_key_rejected_by_struct_schema():
    with pytest.raises((ConfigKeyError, ConfigAttributeError, Exception)):
        _compose(["train.nope=1"])


def test_default_model_is_config_source():
    cfg = _compose()
    assert cfg.model.source == "config"
    assert cfg.model.num_classes >= 1


def test_hub_model_variant_has_fetch_fields():
    cfg = _compose(["model=superanimal_bird"])
    assert cfg.model.source == "hub"
    assert cfg.model.repo_id
    assert list(cfg.model.files)
    assert cfg.model.weights_dir
