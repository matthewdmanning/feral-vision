"""Contracts for external model-source adapters; HF tests use the real client."""

from __future__ import annotations

# stdlib
import sys
from types import ModuleType, SimpleNamespace

# third-party
import pytest
import torch
from huggingface_hub import constants as hf_constants
from huggingface_hub.errors import OfflineModeIsEnabled
from omegaconf import OmegaConf
from torch import nn

# project
from feral_vision.models.sources.HFAdapter import HFAdapter
from feral_vision.models.sources.SourceAdapter import SourceAdapter
from feral_vision.models.sources.TorchHubAdapter import TorchHubAdapter
from feral_vision.models.sources.UltralyticsAdapter import UltralyticsAdapter
from feral_vision.tasks import CVTask

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _make_cfg(
    source: str,
    model_id: str,
    *,
    weights: dict | None = None,
    num_classes: int | None = None,
):
    """Build a ModelConfig-shaped adapter input without composing the full recipe."""
    return OmegaConf.create(
        {
            "architecture": {
                "source": source,
                "id": model_id,
                "location": "hub",
                "num_classes": num_classes,
            },
            "weights": weights,
        }
    )


# ---------------------------------------------------------------------------
# HFAdapter — metadata and cached-weight contracts
# ---------------------------------------------------------------------------


# Hugging Face's own testing org hosts a stable, tiny, public repo for exactly
# this purpose, so these tests call the real huggingface_hub client.
HF_TESTING_REPO = "hf-internal-testing/tiny-random-ViTForImageClassification"


@pytest.mark.network
def test_hf_adapter_inspect_maps_real_hub_metadata_to_project_model_properties():
    properties, metadata = HFAdapter().inspect(_make_cfg("hf_hub", HF_TESTING_REPO))

    assert properties.model_outputs == [CVTask.CLASSIFICATION]
    assert metadata["pipeline_tag"] == "image-classification"
    assert "vit" in metadata["tags"]
    assert metadata["config"]["model_type"] == "vit"


@pytest.mark.network
def test_hf_adapter_downloads_only_weight_files_missing_from_the_destination(tmp_path):
    destination = tmp_path / "weights"
    destination.mkdir()
    (destination / "config.json").write_bytes(b"cached")

    HFAdapter().fetch(
        _make_cfg(
            "hf_hub",
            HF_TESTING_REPO,
            weights={
                "id": ["pytorch_model.bin", "config.json"],
                "location": str(destination),
            },
        )
    )

    assert (destination / "pytorch_model.bin").stat().st_size > 0
    assert (destination / "config.json").read_bytes() == b"cached"


def test_hf_adapter_explains_how_to_recover_when_the_hub_is_unreachable(monkeypatch):
    # The documented switch for "no HTTP calls": the real client then raises
    # huggingface_hub.errors.OfflineModeIsEnabled from model_info.
    monkeypatch.setattr(hf_constants, "HF_HUB_OFFLINE", True)

    with pytest.raises(RuntimeError, match="pass fetch_if_needed=True") as raised:
        HFAdapter().inspect(_make_cfg("hf_hub", HF_TESTING_REPO))

    assert isinstance(raised.value.__cause__, OfflineModeIsEnabled)


# ---------------------------------------------------------------------------
# TorchHubAdapter — configured source selection contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "weights,expected_name",
    [
        ({"id": ["configured-model"], "location": None}, "configured-model"),
        (None, "default"),
    ],
)
def test_torch_hub_adapter_uses_configured_model_name_or_default(
    monkeypatch, weights, expected_name
):
    calls: list[tuple[str, str, bool, bool]] = []
    model = nn.Identity()

    def _load(repo: str, name: str, *, verbose: bool, trust_repo: bool) -> nn.Module:
        calls.append((repo, name, verbose, trust_repo))
        return model

    monkeypatch.setattr(torch.hub, "load", _load)

    result = TorchHubAdapter().fetch(
        _make_cfg("torch_hub", "owner/repo", weights=weights)
    )

    assert result is model
    assert calls == [("owner/repo", expected_name, False, True)]


def test_torch_hub_adapter_requires_explicit_local_inspection_fallback(monkeypatch):
    adapter = TorchHubAdapter()
    cfg = _make_cfg("torch_hub", "owner/repo")

    with pytest.raises(RuntimeError, match="pass fetch_if_needed=True"):
        adapter.inspect(cfg)

    monkeypatch.setattr(adapter, "fetch", lambda configured: nn.Linear(3, 2))
    properties, metadata = adapter.inspect(cfg, fetch_if_needed=True)

    assert properties.model_outputs == []
    assert metadata == {}


# ---------------------------------------------------------------------------
# UltralyticsAdapter — task metadata and module extraction contracts
# ---------------------------------------------------------------------------


def test_ultralytics_adapter_returns_module_and_preserves_task_metadata(monkeypatch):
    loaded_module = nn.Conv2d(3, 2, kernel_size=1)

    class _YOLO:
        """Minimal offline Ultralytics facade with a model and task metadata."""

        def __init__(self, model_id: str) -> None:
            self.model = loaded_module
            self.task = "segment"
            self.names = {0: "cat", 1: "dog"}
            self.model.nc = 2

    ultralytics = ModuleType("ultralytics")
    ultralytics.YOLO = _YOLO  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics)
    cfg = _make_cfg("ultralytics", "yolo11n-seg.pt")

    adapter = UltralyticsAdapter()
    assert adapter.fetch(cfg) is loaded_module
    properties, metadata = adapter.inspect(cfg)

    assert properties.model_outputs == [CVTask.SEG_INSTANCE]
    assert metadata == {"task": "segment", "nc": 2, "names": {0: "cat", 1: "dog"}}


def test_ultralytics_adapter_rebuilds_detection_head_for_configured_taxonomy(
    monkeypatch,
):
    pretrained = SimpleNamespace(
        model=[SimpleNamespace(nc=80)],
        yaml={"nc": 80},
    )
    fine_tuning_model = nn.Identity()
    loaded_weights: list[object] = []
    fine_tuning_model.load = lambda weights, verbose: loaded_weights.append(weights)  # type: ignore[attr-defined]

    class _YOLO:
        """Minimal offline facade returning an eighty-class pretrained detector."""

        def __init__(self, model_id: str) -> None:
            self.model = pretrained

    def _detection_model(yaml, *, nc: int, verbose: bool) -> nn.Module:
        """Use this function to capture construction of the configured fine-tuning head."""
        assert yaml == {"nc": 80}
        assert nc == 10
        assert verbose is False
        return fine_tuning_model

    ultralytics = ModuleType("ultralytics")
    ultralytics.__path__ = []  # type: ignore[attr-defined]
    ultralytics.YOLO = _YOLO  # type: ignore[attr-defined]
    ultralytics_nn = ModuleType("ultralytics.nn")
    ultralytics_nn.__path__ = []  # type: ignore[attr-defined]
    ultralytics_tasks = ModuleType("ultralytics.nn.tasks")
    ultralytics_tasks.DetectionModel = _detection_model  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ultralytics", ultralytics)
    monkeypatch.setitem(sys.modules, "ultralytics.nn", ultralytics_nn)
    monkeypatch.setitem(sys.modules, "ultralytics.nn.tasks", ultralytics_tasks)

    assert (
        UltralyticsAdapter().fetch(
            _make_cfg("ultralytics", "yolo11n.pt", num_classes=10)
        )
        is fine_tuning_model
    )
    assert loaded_weights == [pretrained]


# ---------------------------------------------------------------------------
# Model acquisition — dynamic adapter routing contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "adapter_name"),
    [
        ("hf_hub", "HFAdapter"),
        ("torch_hub", "TorchHubAdapter"),
        ("ultralytics", "UltralyticsAdapter"),
    ],
)
def test_get_adapter_discovers_each_declared_source_adapter(source, adapter_name):
    from feral_vision.models.register_model import get_adapter

    adapter = get_adapter(source)

    assert isinstance(adapter, SourceAdapter)
    assert type(adapter).__name__ == adapter_name


def test_get_adapter_explains_how_to_add_an_unknown_source_adapter():
    from feral_vision.models.register_model import get_adapter

    with pytest.raises(KeyError, match="no adapter for source 'unknown_source'"):
        get_adapter("unknown_source")


def test_model_builder_delegates_remote_architecture_to_selected_adapter(monkeypatch):
    from feral_vision.models import register_model

    expected_model = nn.Identity()
    calls: list[object] = []

    class _Adapter:
        """Minimal source adapter proving the builder's delegation boundary."""

        def fetch(self, cfg):
            calls.append(cfg)
            return expected_model

    cfg = _make_cfg("hf_hub", "owner/model")
    monkeypatch.setattr(register_model, "get_adapter", lambda source: _Adapter())

    model = register_model.model_builder(cfg)

    assert model is expected_model
    assert calls == [cfg]
