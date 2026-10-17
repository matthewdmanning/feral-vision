"""Offline contracts for model-source adapters using API-checked library mocks."""

from __future__ import annotations

# stdlib
import importlib
from unittest.mock import create_autospec

# third-party
import pytest
import torch
import ultralytics
import ultralytics.nn.tasks as ultralytics_tasks
from huggingface_hub import ModelInfo
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


@pytest.fixture
def unregistered_model(monkeypatch):
    """Keep metadata inspection independent of external MLflow registry state."""
    from feral_vision.models import register_model

    lookup = create_autospec(
        register_model.load_model_registry, side_effect=KeyError("unregistered")
    )
    monkeypatch.setattr(register_model, "load_model_registry", lookup)


@pytest.mark.parametrize(
    "pipeline_tag,expected_outputs",
    [
        ("image-classification", [CVTask.CLASSIFICATION]),
        ("object-detection", [CVTask.DETECTION]),
        ("semantic-segmentation", [CVTask.SEG_SEMANTIC]),
        ("instance-segmentation", [CVTask.SEG_INSTANCE]),
        ("image-segmentation", [CVTask.SEG_SEMANTIC, CVTask.SEG_INSTANCE]),
    ],
)
def test_hf_adapter_maps_hub_metadata_to_project_tasks(
    monkeypatch, unregistered_model, pipeline_tag, expected_outputs
):
    hub = importlib.import_module("feral_vision.models.sources.HFAdapter")
    info = ModelInfo(
        id="test/vision-model",
        pipeline_tag=pipeline_tag,
        tags=["vision"],
        config={"model_type": "test-architecture"},
    )
    model_info = create_autospec(hub.model_info, return_value=info)
    monkeypatch.setattr(hub, "model_info", model_info)

    properties, metadata = HFAdapter().inspect(_make_cfg("hf_hub", "test/vision-model"))

    model_info.assert_called_once_with("test/vision-model")
    assert properties.model_outputs == expected_outputs
    assert metadata == {
        "pipeline_tag": pipeline_tag,
        "tags": ["vision"],
        "config": {"model_type": "test-architecture"},
    }


def test_hf_adapter_requests_only_weight_files_missing_from_destination(
    tmp_path, monkeypatch
):
    hub = importlib.import_module("feral_vision.models.sources.HFAdapter")
    destination = tmp_path / "weights"
    destination.mkdir()
    (destination / "config.json").write_bytes(b"cached")
    download = create_autospec(hub.hf_hub_download)
    model = nn.Identity()
    load = create_autospec(hub._load_local, return_value=model)
    monkeypatch.setattr(hub, "hf_hub_download", download)
    monkeypatch.setattr(hub, "_load_local", load)

    result = HFAdapter().fetch(
        _make_cfg(
            "hf_hub",
            "test/vision-model",
            weights={
                "id": ["pytorch_model.bin", "config.json"],
                "location": str(destination),
            },
        )
    )

    assert result is model
    download.assert_called_once_with(
        repo_id="test/vision-model", filename="pytorch_model.bin", local_dir=destination
    )
    load.assert_called_once_with(
        destination, ["pytorch_model.bin", "config.json"], task=None
    )
    assert (destination / "config.json").read_bytes() == b"cached"


def test_hf_adapter_explains_how_to_recover_when_the_hub_is_unreachable(
    monkeypatch, unregistered_model
):
    hub = importlib.import_module("feral_vision.models.sources.HFAdapter")
    info = create_autospec(hub.model_info, side_effect=OfflineModeIsEnabled("offline"))
    monkeypatch.setattr(hub, "model_info", info)

    with pytest.raises(RuntimeError, match="pass fetch_if_needed=True") as raised:
        HFAdapter().inspect(_make_cfg("hf_hub", "test/vision-model"))

    assert isinstance(raised.value.__cause__, OfflineModeIsEnabled)


@pytest.mark.parametrize(
    "task,class_name",
    [
        ("classification", "AutoModelForImageClassification"),
        ("detection", "AutoModelForObjectDetection"),
        ("semantic_segmentation", "AutoModelForSemanticSegmentation"),
        ("instance_segmentation", "AutoModelForInstanceSegmentation"),
        ("panoptic_segmentation", "AutoModelForUniversalSegmentation"),
        ("pose", "AutoModelForPoseEstimation"),
    ],
)
def test_hf_uses_selected_task_head_and_native_loading_options(
    monkeypatch, task, class_name
):
    """Hydra's selected task chooses the upstream task class without fetching real weights."""
    import transformers

    model_class = getattr(transformers, class_name)
    expected = nn.Identity()
    load = create_autospec(model_class.from_pretrained, return_value=expected)
    monkeypatch.setattr(model_class, "from_pretrained", load)
    cfg = _make_cfg("hf_hub", "test/model", num_classes=3)
    cfg.architecture.kwargs = {"ignore_mismatched_sizes": True}

    result = HFAdapter().fetch(cfg, task=task)

    assert result is expected
    load.assert_called_once_with(
        "test/model", num_labels=3, ignore_mismatched_sizes=True
    )


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
    model = nn.Identity()
    load = create_autospec(torch.hub.load, return_value=model)
    monkeypatch.setattr(torch.hub, "load", load)

    result = TorchHubAdapter().fetch(
        _make_cfg("torch_hub", "owner/repo", weights=weights)
    )

    assert result is model
    load.assert_called_once_with(
        "owner/repo", expected_name, verbose=False, trust_repo=True
    )


def test_torch_hub_adapter_requires_explicit_local_inspection_fallback(
    monkeypatch, unregistered_model
):
    adapter = TorchHubAdapter()
    cfg = _make_cfg("torch_hub", "owner/repo")

    with pytest.raises(RuntimeError, match="pass fetch_if_needed=True"):
        adapter.inspect(cfg)

    monkeypatch.setattr(
        adapter, "fetch", lambda configured: nn.Conv2d(3, 2, kernel_size=1)
    )
    properties, metadata = adapter.inspect(cfg, fetch_if_needed=True)

    assert properties.model_outputs == []
    assert metadata == {}


# ---------------------------------------------------------------------------
# UltralyticsAdapter — task metadata and module extraction contracts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task,expected_output",
    [
        ("detect", CVTask.DETECTION),
        ("segment", CVTask.SEG_INSTANCE),
        ("classify", CVTask.CLASSIFICATION),
    ],
)
def test_ultralytics_adapter_returns_module_and_preserves_task_metadata(
    monkeypatch, unregistered_model, task, expected_output
):
    loaded_module = nn.Conv2d(3, 2, kernel_size=1)

    yolo = create_autospec(ultralytics.YOLO)
    yolo.return_value.model = loaded_module
    yolo.return_value.task = task
    yolo.return_value.names = {0: "cat", 1: "dog"}
    loaded_module.nc = 2
    monkeypatch.setattr(ultralytics, "YOLO", yolo)
    cfg = _make_cfg("ultralytics", "yolo11n-seg.pt")

    adapter = UltralyticsAdapter()
    assert adapter.fetch(cfg) is loaded_module
    properties, metadata = adapter.inspect(cfg)

    assert properties.model_outputs == [expected_output]
    assert metadata == {"task": task, "nc": 2, "names": {0: "cat", 1: "dog"}}


@pytest.mark.parametrize(
    "task,model_class",
    [
        ("detect", ultralytics_tasks.DetectionModel),
        ("segment", ultralytics_tasks.SegmentationModel),
        ("pose", ultralytics_tasks.PoseModel),
    ],
)
def test_ultralytics_adapter_preserves_task_when_rebuilding_configured_head(
    monkeypatch,
    task,
    model_class,
):
    head = nn.Identity()
    head.nc = 80
    pretrained = nn.Module()
    pretrained.model = nn.ModuleList([head])
    pretrained.yaml = {"nc": 80}
    fine_tuning_model = create_autospec(model_class, instance=True)
    detection_model = create_autospec(model_class, return_value=fine_tuning_model)
    yolo = create_autospec(ultralytics.YOLO)
    yolo.return_value.model = pretrained
    yolo.return_value.task = task
    yolo.return_value.task_map = {task: {"model": detection_model}}
    monkeypatch.setattr(ultralytics, "YOLO", yolo)

    assert (
        UltralyticsAdapter().fetch(
            _make_cfg("ultralytics", "yolo11n.pt", num_classes=10)
        )
        is fine_tuning_model
    )
    yolo.assert_called_once_with("yolo11n.pt")
    detection_model.assert_called_once_with({"nc": 80}, nc=10, verbose=False)
    fine_tuning_model.load.assert_called_once_with(pretrained, verbose=False)


def test_ultralytics_classifier_uses_native_head_adjustment(monkeypatch):
    """Classification delegates head adjustment to Ultralytics rather than assuming `.nc`."""
    model = nn.Conv2d(3, 2, 1)
    yolo = create_autospec(ultralytics.YOLO)
    yolo.return_value.model = model
    yolo.return_value.task = "classify"
    reshape = create_autospec(ultralytics_tasks.ClassificationModel.reshape_outputs)
    monkeypatch.setattr(ultralytics, "YOLO", yolo)
    monkeypatch.setattr(
        ultralytics_tasks.ClassificationModel, "reshape_outputs", reshape
    )

    result = UltralyticsAdapter().fetch(
        _make_cfg("ultralytics", "test-cls.pt", num_classes=3)
    )

    assert result is model
    reshape.assert_called_once_with(model, 3)


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
    adapter = create_autospec(SourceAdapter, instance=True, spec_set=True)
    adapter.fetch.return_value = expected_model
    cfg = _make_cfg("hf_hub", "owner/model")
    get_adapter = create_autospec(register_model.get_adapter, return_value=adapter)
    monkeypatch.setattr(register_model, "get_adapter", get_adapter)

    model = register_model.model_builder(cfg)

    assert model is expected_model
    get_adapter.assert_called_once_with("hf_hub")
    adapter.fetch.assert_called_once_with(cfg)
