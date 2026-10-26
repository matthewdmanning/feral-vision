"""Offline contracts for model-source adapters using API-checked library mocks."""

from __future__ import annotations

# stdlib
import importlib
import json
import base64
import io
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
from sightkit_learn.models.sources.HFAdapter import HFAdapter
from sightkit_learn.models.sources.SourceAdapter import SourceAdapter
from sightkit_learn.models.sources.TorchHubAdapter import TorchHubAdapter
from sightkit_learn.models.sources.UltralyticsAdapter import UltralyticsAdapter
from sightkit_learn.tasks import CVTask

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hub_metadata_transport(monkeypatch):
    """Use this fixture to expose Hub declarations while making execution of the source fail."""
    hub = importlib.import_module("sightkit_learn.models.sources.TorchHubAdapter")
    source = 'from torchvision.models import resnet18, resnet50, vit_b_16\nraise AssertionError("repository code must not execute")\n'
    document = {
        "content": base64.b64encode(source.encode()).decode(),
        "html_url": "https://github.com/pytorch/vision/blob/v0.20.1/hubconf.py",
    }
    transport = create_autospec(
        hub.urlopen,
        side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(document).encode()),
    )
    monkeypatch.setattr(hub, "urlopen", transport)
    return transport


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
                "location": None,
                "num_classes": num_classes,
            },
            "weights": weights,
        }
    )


# ---------------------------------------------------------------------------
# HFAdapter â€” metadata and cached-weight contracts
# ---------------------------------------------------------------------------


@pytest.fixture
def unregistered_model(monkeypatch):
    """Keep metadata inspection independent of external MLflow registry state."""
    from sightkit_learn.models import register_model

    lookup = create_autospec(
        register_model.load_model_registry,
        side_effect=AssertionError("prep must not read MLflow"),
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
    hub = importlib.import_module("sightkit_learn.models.sources.HFAdapter")
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
        "config": {"model_type": "test-architecture"},
        "available_weights": [],
    }


def test_hf_adapter_requests_only_weight_files_missing_from_destination(
    tmp_path, monkeypatch
):
    hub = importlib.import_module("sightkit_learn.models.sources.HFAdapter")
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


def test_hf_inspection_reads_class_information_without_fetching_weights(
    tmp_path, monkeypatch, unregistered_model
):
    """Use this function to verify Hub config and weight choices remain provider facts."""
    hub = importlib.import_module("sightkit_learn.models.sources.HFAdapter")
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "num_labels": 2,
                "id2label": {"0": "cat", "1": "dog"},
                "unrelated_training_history": "discard",
            }
        ),
        encoding="utf-8",
    )
    info = ModelInfo(
        id="test/classifier",
        sha="provider-revision",
        pipeline_tag="image-classification",
        siblings=[
            {"rfilename": name}
            for name in [
                "config.json",
                "model.safetensors",
                "pytorch_model.bin",
                "README.md",
            ]
        ],
    )
    monkeypatch.setattr(
        hub, "model_info", create_autospec(hub.model_info, return_value=info)
    )
    download = create_autospec(hub.hf_hub_download, return_value=str(config_path))
    monkeypatch.setattr(hub, "hf_hub_download", download)
    props, metadata = HFAdapter().inspect(_make_cfg("hf_hub", "test/classifier"))
    assert props.model_outputs == [CVTask.CLASSIFICATION]
    assert metadata["config"] == {"num_labels": 2, "id2label": {"0": "cat", "1": "dog"}}
    assert metadata["available_weights"] == ["model.safetensors", "pytorch_model.bin"]
    download.assert_called_once_with(
        repo_id="test/classifier", filename="config.json", revision=info.sha
    )


def test_hf_adapter_explains_how_to_recover_when_the_hub_is_unreachable(
    monkeypatch, unregistered_model
):
    hub = importlib.import_module("sightkit_learn.models.sources.HFAdapter")
    info = create_autospec(hub.model_info, side_effect=OfflineModeIsEnabled("offline"))
    monkeypatch.setattr(hub, "model_info", info)

    with pytest.raises(RuntimeError, match="could not inspect") as raised:
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
# TorchHubAdapter â€” configured source selection contract
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


def test_ultralytics_adapter_fetch_returns_native_module(monkeypatch):
    """Use this function to verify training acquisition still returns the native module."""
    model = nn.Identity()
    constructor = create_autospec(ultralytics.YOLO)
    constructor.return_value.model = model
    monkeypatch.setattr(ultralytics, "YOLO", constructor)
    assert UltralyticsAdapter().fetch(_make_cfg("ultralytics", "yolo11n.pt")) is model


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
# Model acquisition â€” dynamic adapter routing contract
# ---------------------------------------------------------------------------


def test_hf_discovery_uses_provider_search_and_task_filters(monkeypatch):
    """Use this function to verify Hub discovery returns identifiers suitable for inspection."""
    import huggingface_hub

    api = create_autospec(huggingface_hub.HfApi, instance=True)
    api.list_models.return_value = iter(
        [ModelInfo(id="provider/vision-model", pipeline_tag="object-detection")]
    )
    constructor = create_autospec(huggingface_hub.HfApi, return_value=api)
    monkeypatch.setattr(huggingface_hub, "HfApi", constructor)
    candidates = list(
        HFAdapter().list_models(
            query="vision", repository="provider", pipeline_tag="object-detection"
        )
    )
    assert candidates == [
        {
            "model_id": "provider/vision-model",
            "architecture_location": "https://huggingface.co/provider/vision-model",
            "pipeline_tag": "object-detection",
        }
    ]
    api.list_models.assert_called_once_with(
        search="vision",
        author="provider",
        pipeline_tag="object-detection",
        sort="downloads",
    )


@pytest.mark.parametrize(
    "query,expected_names",
    [
        (None, ["resnet18", "resnet50", "vit_b_16"]),
        ("resnet", ["resnet18", "resnet50"]),
    ],
)
def test_torch_hub_discovery_returns_repository_entrypoints(
    monkeypatch, hub_metadata_transport, query, expected_names
):
    """Use this function to verify Torch Hub discovery keeps repositories and model entrypoints distinct."""
    candidates = list(
        TorchHubAdapter().list_models(repository="pytorch/vision:v0.20.1", query=query)
    )
    assert [row["architecture_location"] for row in candidates] == expected_names
    assert all(row["model_id"] == "pytorch/vision:v0.20.1" for row in candidates)


def test_ultralytics_architecture_inspection_reports_weight_options_without_inventing_labels(
    monkeypatch,
):
    """Use this function to distinguish architecture defaults from pretrained class vocabulary."""
    constructor = create_autospec(
        ultralytics.YOLO, side_effect=AssertionError("prep must not construct a model")
    )
    monkeypatch.setattr(ultralytics, "YOLO", constructor)
    props, metadata = UltralyticsAdapter().inspect(
        _make_cfg("ultralytics", "cfg/models/11/yolo11.yaml")
    )
    assert props.model_outputs == [CVTask.DETECTION]
    assert metadata["names"] is None
    assert metadata["nc"] == 80
    assert metadata["available_weights"] == sorted(
        f"yolo11{scale}.pt" for scale in "nsmlx"
    )
    constructor.assert_not_called()


def test_torch_hub_inspection_reports_torchvision_weight_options(
    monkeypatch, hub_metadata_transport
):
    """Use this function to gather published TorchVision weight metadata without constructing a model."""
    import torchvision

    load = create_autospec(
        torch.hub.load, side_effect=AssertionError("prep must not load models")
    )
    monkeypatch.setattr(torch.hub, "load", load)
    cfg = _make_cfg("torch_hub", "pytorch/vision:v0.20.1")
    cfg.architecture.location = "resnet18"
    props, metadata = TorchHubAdapter().inspect(cfg)
    assert props.model_outputs == [CVTask.CLASSIFICATION]
    assert metadata["available_weights"] == [
        {"id": weight.name, "location": weight.url}
        for weight in torchvision.models.ResNet18_Weights
    ]
    assert len(metadata["names"]) == metadata["nc"] == 1000
    load.assert_not_called()


def test_ultralytics_discovery_includes_architectures_and_checkpoint_families():
    """Use this function to verify the installed catalogue exposes more than a single YOLO checkpoint."""
    rows = list(UltralyticsAdapter().list_models())
    by_id = {row["model_id"]: row for row in rows}
    for model_id, location in {
        "yolo11n.pt": "YOLO",
        "yolo11x-seg.pt": "YOLO",
        "rtdetr-l.pt": "RTDETR",
        "sam_b.pt": "SAM",
        "FastSAM-s.pt": "FastSAM",
        "yolo_nas_s.pt": "NAS",
    }.items():
        assert by_id[model_id]["architecture_location"] == "ultralytics." + location
        assert by_id[model_id]["kind"] == "checkpoint"
    assert by_id["cfg/models/11/yolo11.yaml"]["kind"] == "architecture"
    filtered = list(UltralyticsAdapter().list_models(query="yolo11"))
    assert filtered
    assert all("yolo11" in row["model_id"].casefold() for row in filtered)
    assert not list(UltralyticsAdapter().list_models(query="absent-model-family"))


@pytest.mark.parametrize(
    "class_name,model_id,task,expected_output",
    [
        ("SAM", "sam_b.pt", "segment", CVTask.SEG_INSTANCE),
        ("FastSAM", "FastSAM-s.pt", "segment", CVTask.SEG_INSTANCE),
        ("NAS", "yolo_nas_s.pt", "detect", CVTask.DETECTION),
        ("RTDETR", "rtdetr-l.pt", "detect", CVTask.DETECTION),
    ],
)
def test_ultralytics_inspection_reads_metadata_without_constructing_models(
    monkeypatch, class_name, model_id, task, expected_output
):
    """Use this function to gather native constructor documentation without constructing a model."""
    constructor = create_autospec(
        getattr(ultralytics, class_name),
        side_effect=AssertionError("prep must not construct a model"),
    )
    monkeypatch.setattr(ultralytics, class_name, constructor)
    cfg = _make_cfg("ultralytics", model_id)
    cfg.architecture.location = "ultralytics." + class_name
    props, metadata = UltralyticsAdapter().inspect(cfg)
    constructor.assert_not_called()
    assert props.model_outputs == [expected_output]
    assert metadata["architecture_location"] == cfg.architecture.location
    assert metadata["names"] is None


@pytest.mark.parametrize(
    ("source", "adapter_name"),
    [
        ("hf_hub", "HFAdapter"),
        ("torch_hub", "TorchHubAdapter"),
        ("ultralytics", "UltralyticsAdapter"),
    ],
)
def test_get_adapter_discovers_each_declared_source_adapter(source, adapter_name):
    from sightkit_learn.models.register_model import get_adapter

    adapter = get_adapter(source)

    assert isinstance(adapter, SourceAdapter)
    assert type(adapter).__name__ == adapter_name


def test_get_adapter_explains_how_to_add_an_unknown_source_adapter():
    from sightkit_learn.models.register_model import get_adapter

    with pytest.raises(KeyError, match="no adapter for source 'unknown_source'"):
        get_adapter("unknown_source")


def test_model_builder_delegates_remote_architecture_to_selected_adapter(monkeypatch):
    from sightkit_learn.models import register_model

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
